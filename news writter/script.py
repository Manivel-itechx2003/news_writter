import speech_recognition as sr
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
from googletrans import Translator


class NewsDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('news_database.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._initialize_database()

    def _initialize_database(self):
        # Check if table exists and has correct structure
        self.cursor.execute("PRAGMA table_info(news_entries)")
        columns = [col[1] for col in self.cursor.fetchall()]

        if not columns:  # Table doesn't exist
            self.cursor.execute('''CREATE TABLE news_entries
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                 title TEXT NOT NULL,
                                 original_text TEXT NOT NULL,
                                 translated_text TEXT NOT NULL,
                                 source_lang TEXT NOT NULL,
                                 target_lang TEXT NOT NULL,
                                 language,created_at DATETIME NOT NULL)''')
        else:  # Table exists, check for missing columns
            required_columns = ['title', 'original_text', 'translated_text', 'source_lang', 'target_lang', 'created_at','language']
            for col in required_columns:
                if col not in columns:
                    if col == 'title':
                        self.cursor.execute(
                            "ALTER TABLE news_entries ADD COLUMN title TEXT NOT NULL DEFAULT 'Untitled'")
                    elif col == 'source_lang':
                        self.cursor.execute(
                            "ALTER TABLE news_entries ADD COLUMN source_lang TEXT NOT NULL DEFAULT 'en'")
                    elif col == 'target_lang':
                        self.cursor.execute(
                            "ALTER TABLE news_entries ADD COLUMN target_lang TEXT NOT NULL DEFAULT 'ta'")
                    elif col == 'created_at':
                        self.cursor.execute(
                            "ALTER TABLE news_entries ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")

        self.conn.commit()

    def save_entry(self, title, original, translated, source_lang, target_lang):
        try:
            self.cursor.execute('''INSERT INTO news_entries 
                                (title, original_text, translated_text, source_lang, target_lang, created_at)
                                VALUES (?, ?, ?, ?, ?, ?)''',
                                (title, original, translated, source_lang, target_lang, datetime.now()))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            self.conn.rollback()
            return False

    def get_all_titles(self):
        try:
            self.cursor.execute("SELECT id, title, created_at FROM news_entries ORDER BY created_at DESC")
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def get_entry(self, entry_id):
        try:
            self.cursor.execute("SELECT * FROM news_entries WHERE id=?", (entry_id,))
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def close(self):
        self.conn.close()


class NewsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sathishkumar News Assistant")
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_listening = False
        self.translator = Translator()
        self.current_language = 'ta'  # Default to Tamil
        self.db = NewsDatabase()  # Initialize database connection

        self.create_widgets()
        self.create_menu()

    def create_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Fetch Previous Work", command=self.fetch_previous_work)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.cleanup_and_exit)
        menubar.add_cascade(label="File", menu=file_menu)

        self.root.config(menu=menubar)

    def cleanup_and_exit(self):
        self.db.close()
        self.root.quit()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title Entry
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=5)
        ttk.Label(title_frame, text="Title:").pack(side=tk.LEFT)
        self.title_entry = ttk.Entry(title_frame, width=50)
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Language selection
        lang_frame = ttk.LabelFrame(main_frame, text="Language Selection", padding="10")
        lang_frame.pack(fill=tk.X, pady=5)

        self.lang_var = tk.StringVar(value='ta')
        ttk.Radiobutton(lang_frame, text="Tamil", variable=self.lang_var,
                        value='ta', command=self.language_changed).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(lang_frame, text="English", variable=self.lang_var,
                        value='en', command=self.language_changed).pack(side=tk.LEFT, padx=10)

        # Text Display Areas
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Original Text
        orig_frame = ttk.LabelFrame(text_frame, text="Original Text", padding="5")
        orig_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        self.orig_text = tk.Text(orig_frame, height=10, width=30, font=('Arial', 12), wrap=tk.WORD)
        scroll_orig = ttk.Scrollbar(orig_frame, orient=tk.VERTICAL, command=self.orig_text.yview)
        self.orig_text.configure(yscrollcommand=scroll_orig.set)

        self.orig_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_orig.pack(side=tk.RIGHT, fill=tk.Y)

        # Translated Text
        trans_frame = ttk.LabelFrame(text_frame, text="Translated Text", padding="5")
        trans_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        self.trans_text = tk.Text(trans_frame, height=10, width=30, font=('Arial', 12), wrap=tk.WORD)
        scroll_trans = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=self.trans_text.yview)
        self.trans_text.configure(yscrollcommand=scroll_trans.set)

        self.trans_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_trans.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind text modification event
        self.orig_text.bind('<KeyRelease>', self.translate_text)

        # Control Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)

        self.start_btn = ttk.Button(btn_frame, text="Start Recording",
                                    command=self.start_recording_thread)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="Stop Recording",
                                   command=self.stop_recognition, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.save_btn = ttk.Button(btn_frame, text="Save to Database",
                                   command=self.save_to_db)
        self.save_btn.pack(side=tk.LEFT, padx=5)

        self.root.geometry("900x600")

    def fetch_previous_work(self):
        entries = self.db.get_all_titles()

        if not entries:
            messagebox.showinfo("Info", "No previous work found")
            return

        select_window = tk.Toplevel(self.root)
        select_window.title("Select Previous Work")

        tree = ttk.Treeview(select_window, columns=('id', 'title', 'date'), show='headings')
        tree.heading('id', text='ID')
        tree.heading('title', text='Title')
        tree.heading('date', text='Date')
        tree.column('id', width=50)
        tree.column('title', width=300)
        tree.column('date', width=150)

        for entry in entries:
            tree.insert('', 'end', values=entry)

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def load_selected():
            selected = tree.focus()
            if not selected:
                return
            item = tree.item(selected)
            entry_id = item['values'][0]

            entry = self.db.get_entry(entry_id)

            if entry:
                self.title_entry.delete(0, tk.END)
                self.title_entry.insert(0, entry[1])
                self.orig_text.delete("1.0", tk.END)
                self.orig_text.insert("1.0", entry[2])
                self.trans_text.delete("1.0", tk.END)
                self.trans_text.insert("1.0", entry[3])
                self.lang_var.set(entry[5])  # Set target language
                select_window.destroy()

        btn_frame = ttk.Frame(select_window)
        btn_frame.pack(pady=5)

        ttk.Button(btn_frame, text="Load Selected", command=load_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=select_window.destroy).pack(side=tk.LEFT, padx=5)

    def language_changed(self):
        self.current_language = self.lang_var.get()
        self.translate_text()

    def translate_text(self, event=None):
        text = self.orig_text.get("1.0", tk.END).strip()
        if not text:
            self.trans_text.delete("1.0", tk.END)
            return

        try:
            if self.current_language == 'ta':
                translated = self.translator.translate(text, src='en', dest='ta').text
            else:
                translated = self.translator.translate(text, src='ta', dest='en').text

            self.trans_text.delete("1.0", tk.END)
            self.trans_text.insert(tk.END, translated)
        except Exception as e:
            messagebox.showerror("Translation Error", f"Could not translate text: {str(e)}")

    def start_recording_thread(self):
        threading.Thread(target=self.start_recording, daemon=True).start()

    def start_recording(self):
        self.is_listening = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=15)
                text = self.recognizer.recognize_google(audio,
                                                        language='en-IN' if self.current_language == 'en' else 'ta-IN')
                self.orig_text.delete("1.0", tk.END)
                self.orig_text.insert(tk.END, text)
                self.translate_text()
            except sr.UnknownValueError:
                messagebox.showerror("Error", "Could not understand audio")
            except sr.RequestError as e:
                messagebox.showerror("Error", f"Service error: {str(e)}")
            except Exception as e:
                messagebox.showerror("Error", f"Unexpected error: {str(e)}")

        self.reset_buttons()

    def reset_buttons(self):
        self.is_listening = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def stop_recognition(self):
        if self.is_listening:
            self.recognizer.stop()
            self.reset_buttons()

    def save_to_db(self):
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Warning", "Please enter a title before saving")
            return

        original = self.orig_text.get("1.0", tk.END).strip()
        translated = self.trans_text.get("1.0", tk.END).strip()

        if not original:
            messagebox.showwarning("Warning", "No content to save!")
            return

        source_lang = 'en' if self.current_language == 'ta' else 'ta'
        target_lang = self.current_language

        success = self.db.save_entry(title, original, translated, source_lang, target_lang)

        if success:
            messagebox.showinfo("Success", "News entry saved successfully!")
        else:
            messagebox.showerror("Error", "Failed to save to database. Check console for details.")


if __name__ == "__main__":
    root = tk.Tk()
    app = NewsApp(root)
    root.protocol("WM_DELETE_WINDOW", app.cleanup_and_exit)
    root.mainloop()