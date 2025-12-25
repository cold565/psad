import os
import shutil
import bcrypt
import psycopg2
from tkinter import *
from tkinter import messagebox, filedialog, simpledialog, ttk



# ===================== Подключение к БД =====================
conn = psycopg2.connect(
    dbname="docuflow",
    user="postgres",
    password="kolya777",
    host="localhost"
)
cur = conn.cursor()

DOCUMENTS_FOLDER = "documents"
os.makedirs(DOCUMENTS_FOLDER, exist_ok=True)

# ===================== Логирование действий =====================
def log_action(user_id, action, document_id=None):
    cur.execute(
        "INSERT INTO activity_log (user_id, action, document_id) VALUES (%s, %s, %s)",
        (user_id, action, document_id)
    )
    conn.commit()

# ===================== Авторизация =====================
class LoginWindow:
    def __init__(self, master):
        self.master = master
        self.master.title("Авторизация")
        self.master.geometry("300x150")
        
        Label(master, text="Логин").pack()
        self.username_entry = Entry(master)
        self.username_entry.pack()

        Label(master, text="Пароль").pack()
        self.password_entry = Entry(master, show="*")
        self.password_entry.pack()

        Button(master, text="Вход", command=self.login).pack(pady=10)

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get().encode('utf-8')

        cur.execute("SELECT id, password_hash, role FROM users WHERE username=%s", (username,))
        result = cur.fetchone()
        if result:
            user_id, password_hash, role = result
            if bcrypt.checkpw(password, password_hash.encode('utf-8')):
                self.master.destroy()
                MainWindow(user_id, username, role)
            else:
                messagebox.showerror("Ошибка", "Неверный пароль")
        else:
            messagebox.showerror("Ошибка", "Пользователь не найден")

# ===================== Главное окно =====================
class MainWindow:
    def __init__(self, user_id, username, role):
        self.user_id = user_id
        self.username = username
        self.role = role

        self.root = Tk()
        self.root.title(f"DocuFlow Главное Меню - {self.role}")
        self.root.geometry("800x600")
        self.root.minsize(800, 600)    # минимальный размер окна
        self.tab_control = ttk.Notebook(self.root)

        # Документы
        self.doc_tab = Frame(self.tab_control)
        self.tab_control.add(self.doc_tab, text="Документы")
        self.setup_documents_tab()

        # Журнал действий
        self.log_tab = Frame(self.tab_control)
        self.tab_control.add(self.log_tab, text="Журнал действий")
        self.setup_log_tab()

        # Пользователи (только для админа)
        if self.role == "admin":
            self.user_tab = Frame(self.tab_control)
            self.tab_control.add(self.user_tab, text="Пользователи")
            self.setup_users_tab()
        

        Button(self.root, text="Сменить пользователя", command=self.switch_user).pack(side=BOTTOM, pady=5)
        Button(self.root, text="Выход из программы", command=self.close_window).pack(side=BOTTOM, pady=8)
        
        self.tab_control.pack(expand=1, fill="both")
        self.root.mainloop()

    # ===================== Документы =====================
    def setup_documents_tab(self):
       # ===== Поиск =====
      search_frame = Frame(self.doc_tab)
      search_frame.pack(fill=X, padx=5, pady=5)

      Label(search_frame, text="Поиск:").pack(side=LEFT, padx=5)

      self.doc_search_entry = Entry(search_frame)
      self.doc_search_entry.pack(side=LEFT, fill=X, expand=True, padx=5)

      Button(search_frame, text="Найти", command=self.search_documents).pack(side=LEFT, padx=5)
      Button(search_frame, text="Сброс", command=self.refresh_documents).pack(side=LEFT, padx=5)
      self.doc_tree = ttk.Treeview(self.doc_tab, columns=("ID", "Title", "Category", "Version"), show="headings")
      self.doc_tree.heading("ID", text="ID")
      self.doc_tree.heading("Title", text="Название")
      self.doc_tree.heading("Category", text="Категория")
      self.doc_tree.heading("Version", text="Версия")
      self.doc_tree.pack(fill=BOTH, expand=True)

      self.doc_tree.bind("<<TreeviewSelect>>", self.show_comments)

      btn_frame = Frame(self.doc_tab)
      btn_frame.pack(pady=5)

      if self.role in ["admin", "manager"]:
          Button(btn_frame, text="Подгрузить", command=self.add_document).pack(side=LEFT, padx=5)
          Button(btn_frame, text="Удалить", command=self.delete_document).pack(side=LEFT, padx=5)
      Button(btn_frame, text="Открыть", command=self.open_document).pack(side=LEFT, padx=5)
      

      if self.role in ["admin", "manager"]:
          Button(btn_frame, text="Обновить версию", command=self.update_document_version).pack(side=LEFT, padx=5)
      

      # Добавляем кнопки для комментариев
      Button(btn_frame, text="Показать комментарии", command=self.show_comments_button).pack(side=LEFT, padx=5)
      Button(btn_frame, text="Добавить комментарий", command=self.add_comment).pack(side=LEFT, padx=5)
      Button(btn_frame, text="Удалить комментарий", command=self.delete_comment).pack(side=LEFT, padx=5)

      self.comment_box = Text(self.doc_tab, height=5)
      self.comment_box.pack(fill=X, padx=5, pady=5)

      self.refresh_documents()

    def search_documents(self):
        query = self.doc_search_entry.get().strip()

        # очищаем таблицу
        for row in self.doc_tree.get_children():
            self.doc_tree.delete(row)

        # если строка пустая — показать все документы
        if not query:
            self.refresh_documents()
            return

        cur.execute("""
            SELECT id, title, category, version
            FROM documents
            WHERE title ILIKE %s OR category ILIKE %s
            ORDER BY id
        """, (f"%{query}%", f"%{query}%"))

        for doc in cur.fetchall():
            self.doc_tree.insert("", END, values=doc)


    def update_document_version(self):
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showwarning("Ошибка", "Выберите документ")
            return

        doc_id = self.doc_tree.item(selected[0])['values'][0]

        if not messagebox.askyesno(
            "Обновить версию",
            "Вы подтверждаете, что документ был изменён и сохранён?"
        ):
            return

        try:
            cur.execute("""
                UPDATE documents
                SET version = version + 1
                WHERE id = %s
                RETURNING title, version
            """, (doc_id,))

            title, new_version = cur.fetchone()
            conn.commit()

            log_action(
                self.user_id,
                f"Обновил версию документа '{title}' до {new_version}",
                doc_id
            )

            self.refresh_documents()
            self.refresh_log()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Ошибка", str(e))

    
    def delete_comment(self):
      selected = self.doc_tree.selection()
      if not selected:
          messagebox.showwarning("Ошибка", "Выберите документ")
          return

      doc_id = self.doc_tree.item(selected[0])['values'][0]

      if not messagebox.askyesno(
          "Удалить комментарий",
          "Будет удалён ваш комментарий к выбранному документу. Продолжить?"
      ):
          return

      try:
          cur.execute("""
              DELETE FROM comments
              WHERE id = (
                  SELECT id FROM comments
                  WHERE document_id = %s AND user_id = %s
                  ORDER BY created_at DESC
                  LIMIT 1
              )
          """, (doc_id, self.user_id))

          if cur.rowcount == 0:
              messagebox.showinfo("Информация", "Комментарий не найден")
              conn.rollback()
              return

          conn.commit()
          log_action(self.user_id, "Удалил комментарий", doc_id)
          self.show_comments(None)
          self.refresh_log()


      except Exception as e:
          conn.rollback()
          messagebox.showerror("Ошибка", str(e))


    def show_comments_button(self):
      """Показывает комментарии для выбранного документа"""
      selected = self.doc_tree.selection()
      if not selected:
          messagebox.showwarning("Ошибка", "Выберите документ")
          return
      doc_id = self.doc_tree.item(selected[0])['values'][0]
      self.comment_box.delete("1.0", END)
      cur.execute("SELECT comment_text, created_at, user_id FROM comments WHERE document_id=%s ORDER BY created_at", (doc_id,))
      comments = cur.fetchall()
      for c in comments:
          user_id = c[2]
          cur.execute("SELECT username FROM users WHERE id=%s", (user_id,))
          username = cur.fetchone()[0]
          self.comment_box.insert(END, f"{c[1]} - {username}: {c[0]}\n")

    def add_comment(self):
        """Добавляет комментарий к выбранному документу"""
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showwarning("Ошибка", "Выберите документ")
            return
        doc_id = self.doc_tree.item(selected[0])['values'][0]
        comment_text = simpledialog.askstring("Комментарий", "Введите текст комментария")
        if comment_text:
            cur.execute(
                "INSERT INTO comments (document_id, user_id, comment_text, created_at) VALUES (%s, %s, %s, NOW())",
                (doc_id, self.user_id, comment_text)
            )
            conn.commit()
            log_action(self.user_id, f"Добавил комментарий к документу ID {doc_id}", doc_id)
            self.show_comments_button()
            self.refresh_log()


    def switch_user(self):
      if messagebox.askyesno("Сменить пользователя", "Вы уверены, что хотите выйти?"):
        self.root.destroy()  # закрываем главное окно
        
        
        root = Tk()
        LoginWindow(root)  # запускаем авторизацию заново
        root.mainloop()

    def close_window(self):
      if messagebox.askyesno("Выйти из программы", "Вы уверены, что хотите выйти?"):
        self.root.destroy()  # закрываем главное окно 


    def refresh_documents(self):
        for row in self.doc_tree.get_children():
            self.doc_tree.delete(row)
        cur.execute("SELECT id, title, category, version FROM documents")
        for doc in cur.fetchall():
            self.doc_tree.insert("", END, values=doc)

    
    def add_document(self):
        file_paths = filedialog.askopenfilenames(
            title="Выберите файлы",
            filetypes=[("All files", "*.*")]
        )

        if not file_paths:
            return

        category = simpledialog.askstring(
            "Категория",
            "Введите категорию для выбранных документов",
            parent=self.root
        )

        if not category:
            return

        for file_path in file_paths:
            filename = os.path.basename(file_path)
            dest_path = os.path.join(DOCUMENTS_FOLDER, filename)

           

            shutil.copy(file_path, dest_path)

            cur.execute("""
                INSERT INTO documents (title, category, file_path, uploaded_by)
                VALUES (%s, %s, %s, %s)
            """, (filename, category, dest_path, self.user_id))

            log_action(self.user_id, f"Добавил документ '{filename}'")

        conn.commit()
        self.refresh_documents()
        self.refresh_log()


    def delete_document(self):
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showwarning("Ошибка", "Выберите документ(ы)")
            return

        for item in selected:
            doc_id = self.doc_tree.item(item)['values'][0]

            # Получаем путь к файлу и название документа
            cur.execute("SELECT file_path, title FROM documents WHERE id=%s", (doc_id,))
            result = cur.fetchone()
            if not result:
                continue
            file_path, title = result

            # Удаляем файл с диска
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось удалить файл: {e}")
                    continue

            # Удаляем запись из БД
            try:
                cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
                conn.commit()
                log_action(self.user_id, f"Удалил документ '{title}'")
            except psycopg2.IntegrityError:
                conn.rollback()
                messagebox.showerror("Ошибка", f"Невозможно удалить документ '{title}': есть связанные записи")
                continue

        # Обновляем отображение
        self.refresh_documents()
        self.comment_box.delete("1.0", END)


    def open_document(self):
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showwarning("Ошибка", "Выберите документ")
            return
        doc_id = self.doc_tree.item(selected[0])['values'][0]
        cur.execute("SELECT file_path, title FROM documents WHERE id=%s", (doc_id,))
        result = cur.fetchone()
        if result:
            file_path, title = result
            if os.path.exists(file_path):
                os.startfile(file_path)
                log_action(self.user_id, f"Открыл документ '{title}'", doc_id)
                self.refresh_log()

            else:
                messagebox.showerror("Ошибка", "Файл не найден")

    def show_comments(self, event):
        selected = self.doc_tree.selection()
        if not selected:
            return
        doc_id = self.doc_tree.item(selected[0])['values'][0]
        self.comment_box.delete("1.0", END)
        cur.execute("SELECT comment_text FROM comments WHERE document_id=%s", (doc_id,))
        comments = cur.fetchall()
        for c in comments:
            self.comment_box.insert(END, c[0] + "\n")

    


    # ===================== Журнал действий =====================
    def setup_log_tab(self):
        self.log_text = Text(self.log_tab)
        self.log_text.pack(fill=BOTH, expand=True)
        
        # Добавляем кнопку очистки журнала только если роль не "user"
        if self.role != "user":
            Button(self.log_tab, text="Очистить", command=self.clear_log).pack(pady=5)
        
        self.refresh_log()

    def refresh_log(self):
        self.log_text.delete("1.0", END)
        cur.execute("""
            SELECT u.username, a.action, a.timestamp FROM activity_log a
            JOIN users u ON a.user_id=u.id
            ORDER BY a.timestamp DESC
        """)
        for row in cur.fetchall():
            self.log_text.insert(END, f"{row[2]} - {row[0]}: {row[1]}\n")

    def clear_log(self):
        # Разрешаем очистку журнала только если роль не "user"
        if self.role == "user":
            messagebox.showwarning("Ограничение", "У вас нет прав для очистки журнала действий.")
            return
        
        if messagebox.askyesno("Очистить", "Вы уверены, что хотите очистить журнал?"):
            cur.execute("DELETE FROM activity_log")
            conn.commit()
            self.refresh_log()


    # ===================== Пользователи =====================
    def setup_users_tab(self):
      self.user_tree = ttk.Treeview(self.user_tab, columns=("ID", "Username", "Role"), show="headings")
      self.user_tree.heading("ID", text="ID")
      self.user_tree.heading("Username", text="Логин")
      self.user_tree.heading("Role", text="Роль")
      self.user_tree.pack(fill=BOTH, expand=True)

      # Кнопки добавления и удаления
      btn_frame = Frame(self.user_tab)
      btn_frame.pack(pady=5)
      Button(btn_frame, text="Добавить пользователя", command=self.add_user).pack(side=LEFT, padx=5)
      Button(btn_frame, text="Удалить пользователя", command=self.delete_user).pack(side=LEFT, padx=5)

      self.refresh_users()

    def add_user(self):
      username = simpledialog.askstring("Добавить пользователя", "Введите логин", parent=self.root)
      if not username:
          return
      password = simpledialog.askstring("Добавить пользователя", "Введите пароль", show="*", parent=self.root)
      if not password:
          return
      role = simpledialog.askstring("Добавить пользователя", "Введите роль (admin, manager, user)", parent=self.root)
      if role not in ["admin", "manager", "user"]:
          messagebox.showerror("Ошибка", "Роль должна быть: admin, manager или user", parent=self.root)
          return

      # Хэширование и добавление в БД
      pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
      try:
          cur.execute(
              "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, NOW())",
              (username, pw_hash, role)
          )
          conn.commit()
          log_action(self.user_id, f"Добавил пользователя '{username}'")
          self.refresh_users()
          self.refresh_log()

      except psycopg2.IntegrityError:
          conn.rollback()
          messagebox.showerror("Ошибка", "Пользователь с таким логином уже существует", parent=self.root)

    
    def delete_user(self):
      selected = self.user_tree.selection()
      if not selected:
          messagebox.showwarning("Ошибка", "Выберите пользователя")
          return

      user_id = self.user_tree.item(selected[0])['values'][0]
      username = self.user_tree.item(selected[0])['values'][1]

      if messagebox.askyesno("Удалить пользователя", f"Вы уверены, что хотите удалить {username}?"):
          try:
              cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
              conn.commit()
              log_action(self.user_id, f"Удалил пользователя '{username}'")
              self.refresh_users()
              self.refresh_log()

          except psycopg2.IntegrityError:
              conn.rollback()
              messagebox.showerror("Ошибка", "Невозможно удалить пользователя, есть связанные записи")


    def refresh_users(self):
        for row in self.user_tree.get_children():
            self.user_tree.delete(row)
        cur.execute("SELECT id, username, role FROM users")
        for user in cur.fetchall():
            self.user_tree.insert("", END, values=user)

# ===================== Запуск программы =====================
if __name__ == "__main__":
    root = Tk()
    app = LoginWindow(root)
    root.mainloop()




