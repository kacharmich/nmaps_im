import json
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET
import requests
from PIL import Image, ImageTk
import threading

BASE_FOLDER = "Приложения/Блокнот картографа Народной карты"

class OSMConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Народная карта - IM")
        self.root.geometry("700x550")
        self.root.configure(bg="#1e1e1e")
        
        # Загрузка фонового изображения
        try:
            self.bg_image = Image.open(r"\proi\Снимок экрана 2023-08-28 171238.png")
            self.bg_image = self.bg_image.resize((700, 550), Image.Resampling.LANCZOS)
            self.bg_image = ImageTk.PhotoImage(self.bg_image)
            self.bg_label = tk.Label(root, image=self.bg_image)
            self.bg_label.place(relwidth=1, relheight=1)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить фоновое изображение: {e}")
        
        self.osm_file_path = ""
        self.folder_name = tk.StringVar(value="Мои адреса")  # Название папки по умолчанию
        self.api_token = tk.StringVar()
        self.progress_text = tk.StringVar(value="Ожидание начала импорта...")
        self.filtered_data = {"paths": {}, "points": {}}  # Данные после фильтрации
        self.streets_list = []  # Список улиц для отображения
        self.selected_streets = set()  # Выбранные улицы
        
        # Основной фрейм для элементов управления
        self.main_frame = tk.Frame(root, bg="#1e1e1e")
        self.main_frame.pack(pady=20)
        
        # Поле для ввода API токена
        tk.Label(self.main_frame, text="API токен Яндекс.Диска:", fg="white", bg="#1e1e1e").grid(row=0, column=0, sticky="w")
        self.api_token_entry = tk.Entry(self.main_frame, textvariable=self.api_token, bg="#333", fg="white", width=40)
        self.api_token_entry.grid(row=0, column=1, padx=10, pady=5)
        tk.Button(self.main_frame, text="Вставить", command=self.paste_from_clipboard, bg="#444", fg="white").grid(row=0, column=2, padx=5)
        
        # Кнопка для выбора OSM файла
        tk.Label(self.main_frame, text="OSM файл:", fg="white", bg="#1e1e1e").grid(row=1, column=0, sticky="w")
        tk.Button(self.main_frame, text="Выбрать файл", command=self.load_osm, bg="#333", fg="white").grid(row=1, column=1, pady=5, sticky="w")
        
        # Поле для ввода названия папки
        tk.Label(self.main_frame, text="Название папки на Яндекс.Диске:", fg="white", bg="#1e1e1e").grid(row=2, column=0, sticky="w")
        self.folder_name_entry = tk.Entry(self.main_frame, textvariable=self.folder_name, bg="#333", fg="white", width=40)
        self.folder_name_entry.grid(row=2, column=1, padx=10, pady=5)
        tk.Button(self.main_frame, text="Вставить", command=self.paste_from_clipboard, bg="#444", fg="white").grid(row=2, column=2, padx=5)
        
        # Кнопки для конвертации и выгрузки
        tk.Button(self.main_frame, text="Сконвертировать", command=self.start_conversion, bg="#555", fg="white").grid(row=3, column=1, pady=10)
        tk.Button(self.main_frame, text="Выгрузить на Яндекс.Диск", command=self.upload_to_yandex, bg="#666", fg="white").grid(row=4, column=1, pady=5)
        
        # Прогресс бар
        self.progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress_bar.pack(pady=10)
        
        # Текстовое поле для вывода результатов
        self.result_text = tk.Text(root, height=10, width=70, bg="#333", fg="white")
        self.result_text.pack(pady=10)
        
        # Метка для отображения прогресса
        self.progress_label = tk.Label(root, textvariable=self.progress_text, fg="white", bg="#1e1e1e")
        self.progress_label.pack()
        
        # Фрейм для списка улиц с прокруткой
        self.streets_frame = tk.Frame(root, bg="#1e1e1e")
        self.streets_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        
        # Canvas и Scrollbar для прокрутки списка улиц
        self.canvas = tk.Canvas(self.streets_frame, bg="#1e1e1e", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.streets_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#1e1e1e")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
    def paste_from_clipboard(self):
        """Вставляет текст из буфера обмена в активное поле ввода."""
        try:
            clipboard_text = self.root.clipboard_get()
            if self.root.focus_get() == self.api_token_entry:
                self.api_token_entry.insert(0, clipboard_text)
            elif self.root.focus_get() == self.folder_name_entry:
                self.folder_name_entry.insert(0, clipboard_text)
        except tk.TclError:
            messagebox.showerror("Ошибка", "Буфер обмена пуст или содержит не текст.")
        
    def load_osm(self):
        file_path = filedialog.askopenfilename(filetypes=[("OSM файлы", "*.osm")])
        if file_path:
            self.osm_file_path = file_path
            messagebox.showinfo("Файл загружен", f"Выбран файл: {file_path}")
        
    def get_address(self, tags):
        street = None
        house_number = None

        for tag in tags:
            key = tag.attrib.get("k", "")
            value = tag.attrib.get("v", "")
            if key == "addr:street":
                street = value
            elif key == "addr:housenumber":
                house_number = value

        if street and house_number:
            return f"{house_number} {street}"  # Номер + улица
        return None
    
    def parse_osm_to_json(self, osm_file):
        tree = ET.parse(osm_file)
        root = tree.getroot()

        points = {}
        total_elements = len(root.findall(".//node")) + len(root.findall(".//way")) + len(root.findall(".//relation"))
        processed_elements = 0

        self.progress_bar["maximum"] = total_elements
        self.progress_bar["value"] = 0

        for element in root.findall(".//node") + root.findall(".//way") + root.findall(".//relation"):
            processed_elements += 1
            self.progress_bar["value"] = processed_elements
            self.progress_text.set(f"Обработка элемента {processed_elements} из {total_elements}...")
            self.root.update_idletasks()  # Обновление интерфейса

            lat = element.attrib.get("lat")
            lon = element.attrib.get("lon")

            if lat is None or lon is None:
                nd = element.find("nd")
                if nd is not None:
                    ref_id = nd.attrib.get("ref")
                    node = root.find(f".//node[@id='{ref_id}']")
                    if node is not None:
                        lat = node.attrib.get("lat")
                        lon = node.attrib.get("lon")

            if lat and lon:
                address = self.get_address(element.findall("tag"))
                if address:
                    unique_id = str(uuid.uuid4())
                    object_type = element.tag  # Тип объекта (node, way, relation)
                    points[unique_id] = {
                        "coords": [float(lon), float(lat)],  # Долгота, широта
                        "desc": address,
                        "type": object_type  # Добавляем тип объекта
                    }

        self.progress_text.set(f"Импортировано {len(points)} адресных точек.")
        return {"paths": {}, "points": points}
    
    def start_conversion(self):
        """Запускает конвертацию в отдельном потоке."""
        if not self.osm_file_path:
            messagebox.showerror("Ошибка", "Выберите файл")
            return
        
        # Отключаем кнопку конвертации, чтобы избежать повторного запуска
        self.main_frame.grid_slaves(row=3, column=1)[0].config(state=tk.DISABLED)
        
        # Запуск конвертации в отдельном потоке
        threading.Thread(target=self.convert_file, daemon=True).start()
    
    def convert_file(self):
        """Конвертирует OSM файл в JSON."""
        json_data = self.parse_osm_to_json(self.osm_file_path)
        output_file = "addresses.json"  # Промежуточный файл
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        # Включаем кнопку конвертации после завершения
        self.main_frame.grid_slaves(row=3, column=1)[0].config(state=tk.NORMAL)
        messagebox.showinfo("Готово", f"Файл сконвертирован в {output_file}")
        
        # Показываем список улиц для фильтрации
        self.show_streets(json_data)
    
    def show_streets(self, json_data):
        """Отображает список улиц для фильтрации."""
        # Очищаем фрейм
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # Собираем улицы и количество адресов
        streets = {}
        for point in json_data["points"].values():
            street = point["desc"].split(" ", 1)[1]  # Убираем номер дома
            if street not in streets:
                streets[street] = 0
            streets[street] += 1
        
        # Отображаем улицы
        self.streets_list = []
        for street, count in streets.items():
            street_frame = tk.Frame(self.scrollable_frame, bg="#1e1e1e")
            street_frame.pack(fill=tk.X, pady=5)
            
            label = tk.Label(street_frame, text=f"{street} ({count} адресов)", fg="white", bg="#1e1e1e")
            label.pack(side=tk.LEFT)
            
            # Кнопка "Добавить"
            add_button = tk.Button(street_frame, text="✓", command=lambda s=street, f=street_frame: self.add_street(s, f), bg="green", fg="white")
            add_button.pack(side=tk.RIGHT, padx=5)
            
            # Кнопка "Исключить"
            remove_button = tk.Button(street_frame, text="✕", command=lambda s=street, f=street_frame: self.remove_street(s, f), bg="red", fg="white")
            remove_button.pack(side=tk.RIGHT)
            
            self.streets_list.append((street, street_frame, add_button, remove_button))
    
    def add_street(self, street, street_frame):
        """Добавляет улицу в отфильтрованные данные."""
        self.selected_streets.add(street)
        street_frame.configure(bg="green")
        messagebox.showinfo("Успех", f"Улица '{street}' добавлена в импорт.")
    
    def remove_street(self, street, street_frame):
        """Исключает улицу из отфильтрованных данных."""
        if messagebox.askyesno("Подтверждение", f"Вы действительно хотите исключить улицу '{street}' из импорта?"):
            self.selected_streets.discard(street)
            street_frame.configure(bg="red")
            messagebox.showinfo("Успех", f"Улица '{street}' исключена из импорта.")
    
    def create_filtered_json(self):
        """Создаёт отфильтрованный файл index.json на основе выбранных улиц."""
        if not self.osm_file_path:
            messagebox.showerror("Ошибка", "Сначала загрузите OSM файл")
            return
        
        # Загружаем промежуточный файл
        with open("addresses.json", "r", encoding="utf-8") as f:
            json_data = json.load(f)
        
        # Фильтруем данные
        filtered_points = {}
        for point_id, point in json_data["points"].items():
            street = point["desc"].split(" ", 1)[1]  # Убираем номер дома
            if street in self.selected_streets:
                filtered_points[point_id] = point
        
        # Сохраняем отфильтрованные данные в index.json
        filtered_data = {"paths": {}, "points": filtered_points}
        with open("index.json", "w", encoding="utf-8") as f:
            json.dump(filtered_data, f, ensure_ascii=False, indent=2)
        
        messagebox.showinfo("Готово", "Файл index.json успешно создан.")
    
    def upload_to_yandex(self):
        """Выгружает отфильтрованные данные на Яндекс.Диск."""
        # Создаём отфильтрованный файл
        self.create_filtered_json()
        
        folder_name = self.folder_name.get()  # Используем указанное название папки
        api_token = self.api_token.get()
        if not folder_name or not api_token:
            messagebox.showerror("Ошибка", "Введите API токен и название папки")
            return
        
        disk_folder = f"{BASE_FOLDER}/{folder_name}"
        headers = {"Authorization": f"OAuth {api_token}"}
        
        # Создание папки на Яндекс.Диске
        try:
            requests.put(f"https://cloud-api.yandex.net/v1/disk/resources?path={disk_folder}", headers=headers)
            upload_url = requests.get(f"https://cloud-api.yandex.net/v1/disk/resources/upload?path={disk_folder}/index.json&overwrite=true", headers=headers).json().get("href")
            
            if upload_url:
                with open("index.json", "rb") as f:
                    requests.put(upload_url, files={"file": f})
                messagebox.showinfo("Готово", "Файл загружен на Яндекс.Диск")
                
                # Вывод результатов в текстовое поле
                self.result_text.delete(1.0, tk.END)
                self.result_text.insert(tk.END, "Результаты выгрузки:\n")
                self.result_text.insert(tk.END, f"- Папка: {disk_folder}\n")
                self.result_text.insert(tk.END, f"- Файл: index.json\n")
            else:
                messagebox.showerror("Ошибка", "Не удалось получить ссылку для загрузки")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при выгрузке: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = OSMConverterApp(root)
    root.mainloop()   