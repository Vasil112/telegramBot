import sys
import subprocess
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QProgressBar, QLabel
from PyQt5.QtCore import QTimer

class BotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Telegram Bot Launcher')
        self.setGeometry(100, 100, 300, 200)

        layout = QVBoxLayout()

        self.status_label = QLabel('Статус: Виключено', self)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar(self)
        layout.addWidget(self.progress_bar)

        self.start_button = QPushButton('Увімкнути', self)
        self.start_button.clicked.connect(self.start_bot)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton('Вимкнути', self)
        self.stop_button.clicked.connect(self.stop_bot)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.bot_process = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)

    def start_bot(self):
        self.status_label.setText('Статус: Запуск...')
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.timer.start(100)  # Оновлюємо прогрес кожні 100 мс

        # Запускаємо бота у окремому процесі
        self.bot_process = subprocess.Popen([sys.executable, 'bot.py'])

    def stop_bot(self):
        self.status_label.setText('Статус: Виключення...')
        self.timer.stop()
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        if self.bot_process:
            self.bot_process.terminate()
            self.bot_process = None

        self.status_label.setText('Статус: Виключено')

    def update_progress(self):
        value = self.progress_bar.value()
        if value < 100:
            self.progress_bar.setValue(value + 1)
        else:
            self.timer.stop()
            self.status_label.setText('Статус: Працює')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = BotApp()
    ex.show()
    sys.exit(app.exec_())