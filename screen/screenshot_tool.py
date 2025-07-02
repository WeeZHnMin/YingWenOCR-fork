import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QMessageBox, 
                            QRubberBand, QDesktopWidget, QColorDialog, QSpinBox,
                            QComboBox, QToolBar, QAction, QMainWindow)
from PyQt5.QtCore import Qt, QRect, QPoint, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import (QPixmap, QPainter, QPen, QColor, QFont, QIcon, 
                        QKeySequence, QCursor, QBrush)
from datetime import datetime
import subprocess
import platform

class ScreenshotArea(QWidget):
    """截图区域选择窗口"""
    screenshot_taken = pyqtSignal(QPixmap)
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background-color:black")
        self.setWindowOpacity(0.3)
        
        # 获取屏幕尺寸
        desktop = QDesktopWidget()
        self.screen_geometry = desktop.screenGeometry()
        self.setGeometry(self.screen_geometry)
        
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = QPoint()
        
        # 截取整个屏幕
        self.full_screenshot = QApplication.primaryScreen().grabWindow(0)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()
    
    def mouseMoveEvent(self, event):
        if self.rubber_band.isVisible():
            self.rubber_band.setGeometry(QRect(self.origin, event.pos()).normalized())
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rubber_band.isVisible():
            rect = self.rubber_band.geometry()
            self.rubber_band.hide()
            
            if rect.width() > 10 and rect.height() > 10:
                # 截取选定区域
                cropped = self.full_screenshot.copy(rect)
                self.screenshot_taken.emit(cropped)
            
            self.close()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

class ImageEditor(QWidget):
    """图片编辑器"""
    def __init__(self, pixmap):
        super().__init__()
        self.original_pixmap = pixmap
        self.current_pixmap = pixmap.copy()
        self.drawing = False
        self.brush_size = 3
        self.brush_color = QColor(255, 0, 0)  # 红色
        self.last_point = QPoint()
        self.draw_mode = "pen"  # pen, rectangle, arrow, text
        self.temp_pixmap = None
        self.start_point = QPoint()
        
        self.setFixedSize(self.current_pixmap.size())
        self.setWindowTitle("编辑截图")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.current_pixmap)
        
        # 绘制临时图形（如矩形框）
        if self.temp_pixmap:
            painter.drawPixmap(0, 0, self.temp_pixmap)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.start_point = event.pos()
            self.last_point = event.pos()
            
            if self.draw_mode in ["rectangle", "arrow"]:
                self.temp_pixmap = self.current_pixmap.copy()
    
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drawing:
            if self.draw_mode == "pen":
                painter = QPainter(self.current_pixmap)
                pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, 
                          Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawLine(self.last_point, event.pos())
                self.last_point = event.pos()
                self.update()
            
            elif self.draw_mode == "rectangle":
                self.temp_pixmap = self.current_pixmap.copy()
                painter = QPainter(self.temp_pixmap)
                pen = QPen(self.brush_color, self.brush_size)
                painter.setPen(pen)
                rect = QRect(self.start_point, event.pos()).normalized()
                painter.drawRect(rect)
                self.update()
            
            elif self.draw_mode == "arrow":
                self.temp_pixmap = self.current_pixmap.copy()
                painter = QPainter(self.temp_pixmap)
                pen = QPen(self.brush_color, self.brush_size)
                painter.setPen(pen)
                painter.drawLine(self.start_point, event.pos())
                # 简单箭头头部
                self.draw_arrow_head(painter, self.start_point, event.pos())
                self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = False
            if self.temp_pixmap and self.draw_mode in ["rectangle", "arrow"]:
                self.current_pixmap = self.temp_pixmap.copy()
                self.temp_pixmap = None
    
    def draw_arrow_head(self, painter, start, end):
        """绘制箭头头部"""
        from math import atan2, cos, sin, pi
        
        angle = atan2((end.y() - start.y()), (end.x() - start.x()))
        arrowhead_length = 10
        arrowhead_angle = pi / 6
        
        # 计算箭头的两个端点
        x1 = end.x() - arrowhead_length * cos(angle - arrowhead_angle)
        y1 = end.y() - arrowhead_length * sin(angle - arrowhead_angle)
        x2 = end.x() - arrowhead_length * cos(angle + arrowhead_angle)
        y2 = end.y() - arrowhead_length * sin(angle + arrowhead_angle)
        
        painter.drawLine(end, QPoint(int(x1), int(y1)))
        painter.drawLine(end, QPoint(int(x2), int(y2)))
    
    def set_brush_size(self, size):
        self.brush_size = size
    
    def set_brush_color(self, color):
        self.brush_color = color
    
    def set_draw_mode(self, mode):
        self.draw_mode = mode
    
    def reset(self):
        self.current_pixmap = self.original_pixmap.copy()
        self.update()

class ScreenshotTool(QMainWindow):
    """主截图工具窗口"""
    def __init__(self):
        super().__init__()
        self.screenshot_area = None
        self.image_editor = None
        self.current_pixmap = None
        
        self.init_ui()
        self.setup_shortcuts()
        
    def init_ui(self):
        self.setWindowTitle("截图工具")
        self.setGeometry(100, 100, 400, 300)
        
        # 创建中央窗口
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建工具栏
        self.create_toolbar()
        
        # 主布局
        main_layout = QVBoxLayout()
        
        # 截图按钮区域
        button_layout = QHBoxLayout()
        
        self.area_screenshot_btn = QPushButton("区域截图 (Ctrl+Shift+A)")
        self.area_screenshot_btn.clicked.connect(self.take_area_screenshot)
        
        self.full_screenshot_btn = QPushButton("全屏截图 (Ctrl+Shift+F)")
        self.full_screenshot_btn.clicked.connect(self.take_full_screenshot)
        
        button_layout.addWidget(self.area_screenshot_btn)
        button_layout.addWidget(self.full_screenshot_btn)
        
        # 预览区域
        self.preview_label = QLabel("点击按钮开始截图")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #ccc;
                border-radius: 10px;
                padding: 20px;
                background-color: #f9f9f9;
            }
        """)
        self.preview_label.setMinimumHeight(200)
        
        # 操作按钮区域
        action_layout = QHBoxLayout()
        
        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self.edit_screenshot)
        self.edit_btn.setEnabled(False)
        
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_screenshot)
        self.save_btn.setEnabled(False)
        
        self.copy_btn = QPushButton("复制到剪贴板")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.copy_btn.setEnabled(False)
        
        action_layout.addWidget(self.edit_btn)
        action_layout.addWidget(self.save_btn)
        action_layout.addWidget(self.copy_btn)
        
        # 添加到主布局
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.preview_label)
        main_layout.addLayout(action_layout)
        
        central_widget.setLayout(main_layout)
        
        # 状态栏
        self.statusBar().showMessage("准备就绪")
    
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = self.addToolBar("工具")
        
        # 截图动作
        area_action = QAction("区域截图", self)
        area_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        area_action.triggered.connect(self.take_area_screenshot)
        toolbar.addAction(area_action)
        
        full_action = QAction("全屏截图", self)
        full_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        full_action.triggered.connect(self.take_full_screenshot)
        toolbar.addAction(full_action)
        
        toolbar.addSeparator()
        
        # 文件动作
        save_action = QAction("保存", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_screenshot)
        toolbar.addAction(save_action)
    
    def setup_shortcuts(self):
        """设置全局快捷键"""
        pass  # PyQt5的全局快捷键需要额外的库支持
    
    def take_area_screenshot(self):
        """区域截图"""
        self.hide()  # 隐藏主窗口
        QTimer.singleShot(200, self.start_area_screenshot)
    
    def start_area_screenshot(self):
        """开始区域截图"""
        self.screenshot_area = ScreenshotArea()
        self.screenshot_area.screenshot_taken.connect(self.on_screenshot_taken)
        self.screenshot_area.showFullScreen()
    
    def take_full_screenshot(self):
        """全屏截图"""
        self.hide()
        QTimer.singleShot(200, self.do_full_screenshot)
    
    def do_full_screenshot(self):
        """执行全屏截图"""
        screen = QApplication.primaryScreen()
        pixmap = screen.grabWindow(0)
        self.on_screenshot_taken(pixmap)
    
    def on_screenshot_taken(self, pixmap):
        """截图完成回调"""
        self.current_pixmap = pixmap
        
        # 显示预览
        scaled_pixmap = pixmap.scaled(
            self.preview_label.size(), 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled_pixmap)
        
        # 启用按钮
        self.edit_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)
        
        # 显示主窗口
        self.show()
        self.raise_()
        self.activateWindow()
        
        self.statusBar().showMessage(f"截图完成 - 尺寸: {pixmap.width()}x{pixmap.height()}")
    
    def edit_screenshot(self):
        """编辑截图"""
        if self.current_pixmap:
            self.image_editor = ImageEditor(self.current_pixmap)
            self.image_editor.show()
            
            # 创建编辑工具窗口
            self.create_edit_toolbar()
    
    def create_edit_toolbar(self):
        """创建编辑工具栏窗口"""
        if not self.image_editor:
            return
            
        toolbar_window = QWidget()
        toolbar_window.setWindowTitle("编辑工具")
        toolbar_window.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        layout = QVBoxLayout()
        
        # 绘图模式选择
        mode_layout = QHBoxLayout()
        mode_combo = QComboBox()
        mode_combo.addItems(["画笔", "矩形框", "箭头"])
        mode_combo.currentTextChanged.connect(self.change_draw_mode)
        mode_layout.addWidget(QLabel("工具:"))
        mode_layout.addWidget(mode_combo)
        
        # 画笔大小
        size_layout = QHBoxLayout()
        size_spinbox = QSpinBox()
        size_spinbox.setRange(1, 20)
        size_spinbox.setValue(3)
        size_spinbox.valueChanged.connect(self.image_editor.set_brush_size)
        size_layout.addWidget(QLabel("大小:"))
        size_layout.addWidget(size_spinbox)
        
        # 颜色选择
        color_layout = QHBoxLayout()
        color_btn = QPushButton("选择颜色")
        color_btn.clicked.connect(self.choose_color)
        color_layout.addWidget(color_btn)
        
        # 操作按钮
        action_layout = QHBoxLayout()
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self.image_editor.reset)
        
        finish_btn = QPushButton("完成编辑")
        finish_btn.clicked.connect(lambda: self.finish_editing(toolbar_window))
        
        action_layout.addWidget(reset_btn)
        action_layout.addWidget(finish_btn)
        
        layout.addLayout(mode_layout)
        layout.addLayout(size_layout)
        layout.addLayout(color_layout)
        layout.addLayout(action_layout)
        
        toolbar_window.setLayout(layout)
        toolbar_window.show()
        
        # 保存引用
        self.edit_toolbar = toolbar_window
    
    def change_draw_mode(self, text):
        """改变绘图模式"""
        mode_map = {"画笔": "pen", "矩形框": "rectangle", "箭头": "arrow"}
        if self.image_editor:
            self.image_editor.set_draw_mode(mode_map.get(text, "pen"))
    
    def choose_color(self):
        """选择颜色"""
        color = QColorDialog.getColor()
        if color.isValid() and self.image_editor:
            self.image_editor.set_brush_color(color)
    
    def finish_editing(self, toolbar_window):
        """完成编辑"""
        if self.image_editor:
            self.current_pixmap = self.image_editor.current_pixmap.copy()
            
            # 更新预览
            scaled_pixmap = self.current_pixmap.scaled(
                self.preview_label.size(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled_pixmap)
            
            # 关闭编辑器
            self.image_editor.close()
            toolbar_window.close()
            
            self.statusBar().showMessage("编辑完成")
    
    def save_screenshot(self):
        """保存截图"""
        if not self.current_pixmap:
            return
        
        # 生成默认文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"screenshot_{timestamp}.png"
        
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "保存截图", 
            default_filename,
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if filename:
            success = self.current_pixmap.save(filename)
            if success:
                self.statusBar().showMessage(f"已保存到: {filename}")
                QMessageBox.information(self, "成功", f"截图已保存到:\n{filename}")
            else:
                QMessageBox.warning(self, "错误", "保存失败!")
    
    def copy_to_clipboard(self):
        """复制到剪贴板"""
        if self.current_pixmap:
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(self.current_pixmap)
            self.statusBar().showMessage("已复制到剪贴板")
            QMessageBox.information(self, "成功", "截图已复制到剪贴板!")

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("截图工具")
    app.setApplicationVersion("1.0")
    
    # 设置应用图标（如果有的话）
    # app.setWindowIcon(QIcon("icon.png"))
    
    tool = ScreenshotTool()
    tool.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()