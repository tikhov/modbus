import os

from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from resources import ASSETS_DIR


class SourceTableWidget(QWidget):
    def __init__(self, source_controller=None, parent=None):
        super().__init__(parent)
        self.source = source_controller
        self._setup_ui()
        self._update_table()
        self._meas = None

    def _setup_ui(self):
        # ВНЕШНИЙ layout
        outer_layout = QVBoxLayout(self)
        # увеличить отступ сверху на 30px
        outer_layout.setContentsMargins(16, 50, 16, 16)
        outer_layout.setSpacing(0)

        # Табличный layout
        table_layout = QGridLayout()
        table_layout.setSpacing(0)
        table_layout.setContentsMargins(0, 0, 0, 0)

        # Заголовки
        headers = [
            "Наименование источника",
            "Номер источника (ID)",
            "Ток уставки, А",
            "Напряжение уставки, В",
            "Измеряемый ток, А",
            "Измеряемое напряжение, В",
            "Ампер часы",
            ""
        ]

        header_font = QFont()
        header_font.setBold(True)
        # увеличить размер шрифта заголовков
        header_font.setPointSize(15)

        for col, text in enumerate(headers):
            label = QLabel(text)
            label.setFont(header_font)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                "color: #FFFFFF; background: rgba(0,0,0,0.2); padding: 4px; border-radius: 4px;"
            )
            label.setFixedHeight(40)  # увеличить высоту строки для более крупного шрифта
            table_layout.addWidget(label, 0, col)

        # Данные (2 строки)
        self._data_labels = {}
        # шрифт для значений таблицы
        data_font = QFont()
        data_font.setPointSize(15)

        for row in range(1, 3):
            for col in range(8):
                if col == 7:
                    icon_label = QLabel()
                    icon = QIcon(os.path.join(ASSETS_DIR, "icons", "plot.svg"))
                    icon_label.setPixmap(icon.pixmap(20, 20))
                    icon_label.setAlignment(Qt.AlignCenter)
                    icon_label.setCursor(Qt.PointingHandCursor)
                    icon_label.mousePressEvent = lambda e, r=row: self._on_graph_clicked(r)
                    icon_label.setFixedHeight(36)
                    table_layout.addWidget(icon_label, row, col)
                    self._data_labels[(row, col)] = icon_label
                else:
                    label = QLabel("-")
                    label.setAlignment(Qt.AlignCenter)
                    label.setFont(data_font)
                    label.setStyleSheet("color: #FFFFFF; padding: 4px;")
                    label.setFixedHeight(36)
                    table_layout.addWidget(label, row, col)
                    self._data_labels[(row, col)] = label

        # Столбцы растягиваются, строки фиксированы
        for col in range(8):
            table_layout.setColumnStretch(col, 1)
        for row in range(3):
            table_layout.setRowStretch(row, 0)

        # Добавляем таблицу во внешний layout
        outer_layout.addLayout(table_layout)
        outer_layout.addStretch()  # ← чтобы таблица прилипла к верху

    def _get_table_data(self):
        if self.source is None:
            return [["-", "-", "-", "-", "-", "-", "-"]]
        try:
            v = float(self._meas.voltage)
            i = float(self._meas.current)
            i_i = float(self._meas.current_i) / 10
            v_i = float(self._meas.voltage_i) / 10
            ah_counter = self._meas.ah_counter
            polarity = self._meas.polarity

            v_Text = f"{v:+.1f}".replace("+", "").replace(".", ",")
            i_Text = f"{i:.1f}".replace(".", "")

            i_i_Text = f"{i_i:+.1f}".replace("+", "").replace(".", "")
            v_i_Text = f"{v_i:.1f}".replace(".", ",")

            if polarity == 1:
                i_Text = f"-{i_Text}"
                v_Text = f"-{v_Text}"


            return [["ИПГ 12/5000-380", "10-25-0001", i_i_Text, v_i_Text, i_Text, v_Text, ah_counter]]
        except Exception as e:
            return [["Ошибка", "-", "-", "-", "-", "-", "-"]]

    def _on_graph_clicked(self, row_index):
        print(f"Клик по иконке графика для строки {row_index}")

    def _update_table(self):
        data = self._get_table_data()
        for row_idx, row_data in enumerate(data):
            table_row = row_idx + 1
            for col_idx, value in enumerate(row_data):
                widget = self._data_labels.get((table_row, col_idx))
                if isinstance(widget, QLabel) and col_idx != 7:
                    widget.setText(str(value))

    def refresh(self):
        self._update_table()

    def update_from_meas(self, meas):
        """
        Обновление таблицы по данным измерений.
        meas приходит из AppStore (self.store.measurementsChanged).
        """
        try:
            self._meas = meas
            self._update_table()
        except Exception as e:
            print(f"[SourceTable] Ошибка обновления: {e}")
