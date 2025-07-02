import sys
import os
import time
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QRubberBand, QDesktopWidget)
from PyQt5.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QCursor, QPainter

class ScreenOverlay(QWidget):
    """单个屏幕的覆盖层"""
    selection_started = pyqtSignal(QPoint, int)  # 选择开始位置和屏幕索引
    selection_updated = pyqtSignal(QRect, int)   # 选择区域和屏幕索引
    selection_finished = pyqtSignal(QRect, int)  # 选择完成区域和屏幕索引
    selection_cancelled = pyqtSignal()
    
    def __init__(self, screen_index, screen_geometry, parent=None):
        super().__init__(parent)
        self.screen_index = screen_index
        self.screen_geometry = screen_geometry
        
        # 设置窗口属性
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        self.setWindowOpacity(0.2)
        
        # 设置窗口几何位置
        self.setGeometry(screen_geometry)
        
        # 选择状态
        self.is_selecting = False
        self.origin = QPoint()
        self.current_pos = QPoint()
        
        # 设置光标
        self.setCursor(QCursor(Qt.CrossCursor))
        
        # print(f"创建屏幕 {screen_index} 覆盖层: {screen_geometry.width()}x{screen_geometry.height()} at ({screen_geometry.x()}, {screen_geometry.y()})")
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self.is_selecting = True
            # 转换为全局坐标
            global_pos = self.mapToGlobal(event.pos())
            self.origin = global_pos
            self.selection_started.emit(global_pos, self.screen_index)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.is_selecting:
            # 转换为全局坐标
            global_pos = self.mapToGlobal(event.pos())
            self.current_pos = global_pos
            
            # 创建选择矩形
            rect = QRect(self.origin, self.current_pos).normalized()
            self.selection_updated.emit(rect, self.screen_index)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            # 转换为全局坐标
            global_pos = self.mapToGlobal(event.pos())
            
            # 创建最终选择矩形
            rect = QRect(self.origin, global_pos).normalized()
            
            if rect.width() > 5 and rect.height() > 5:
                self.selection_finished.emit(rect, self.screen_index)
            else:
                self.selection_cancelled.emit()
    
    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key_Escape:
            self.selection_cancelled.emit()
        super().keyPressEvent(event)

class MultiScreenCapture(QWidget):
    """多屏幕截图管理器"""
    screenshot_taken = pyqtSignal(QPixmap)
    screenshot_cancelled = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # 隐藏主窗口
        self.setWindowFlags(Qt.Tool)
        self.hide()
        
        # 获取屏幕信息
        self.setup_screens()
        
        # 创建橡皮筋选择框（全局）
        self.rubber_band = QRubberBand(QRubberBand.Rectangle)
        
        # 预先截取完整屏幕
        self.full_screenshot = self.capture_all_screens()
        
        # 为每个屏幕创建覆盖层
        self.screen_overlays = []
        self.create_screen_overlays()
        
        # 连接信号
        self.connect_overlay_signals()
    
    def setup_screens(self):
        """设置屏幕信息"""
        desktop = QDesktopWidget()
        
        self.screens_info = []
        combined_geometry = None
        
        for i in range(desktop.screenCount()):
            screen_geometry = desktop.screenGeometry(i)
            screen_info = {
                'index': i,
                'geometry': screen_geometry,
                'available_geometry': desktop.availableGeometry(i)
            }
            self.screens_info.append(screen_info)
            
            if combined_geometry is None:
                combined_geometry = screen_geometry
            else:
                combined_geometry = combined_geometry.united(screen_geometry)
        
        self.virtual_desktop_geometry = combined_geometry
        
        # print(f"检测到 {len(self.screens_info)} 个屏幕:")
        for screen in self.screens_info:
            geom = screen['geometry']
            # print(f"  屏幕 {screen['index']}: {geom.width()}x{geom.height()} at ({geom.x()}, {geom.y()})")
    
    def create_screen_overlays(self):
        """为每个屏幕创建覆盖层"""
        for screen_info in self.screens_info:
            overlay = ScreenOverlay(
                screen_info['index'], 
                screen_info['geometry'],
                self
            )
            self.screen_overlays.append(overlay)
    
    def connect_overlay_signals(self):
        """连接覆盖层信号"""
        for overlay in self.screen_overlays:
            overlay.selection_started.connect(self.on_selection_started)
            overlay.selection_updated.connect(self.on_selection_updated)
            overlay.selection_finished.connect(self.on_selection_finished)
            overlay.selection_cancelled.connect(self.on_selection_cancelled)
    
    def capture_all_screens(self):
        """捕获所有屏幕"""
        app = QApplication.instance()
        if not app:
            return QPixmap()
        
        primary_screen = app.primaryScreen()
        virtual_geometry = self.virtual_desktop_geometry
        
        # 尝试直接截取虚拟桌面
        full_pixmap = primary_screen.grabWindow(
            0,
            virtual_geometry.x(),
            virtual_geometry.y(),
            virtual_geometry.width(),
            virtual_geometry.height()
        )
        
        # 如果失败，尝试拼接
        if full_pixmap.isNull() or full_pixmap.width() == 0 or full_pixmap.height() == 0:
            full_pixmap = self.capture_screens_by_stitching()
        
        return full_pixmap
    
    def capture_screens_by_stitching(self):
        """拼接屏幕截图"""
        app = QApplication.instance()
        virtual_geometry = self.virtual_desktop_geometry
        
        result_pixmap = QPixmap(virtual_geometry.width(), virtual_geometry.height())
        result_pixmap.fill(Qt.black)
        
        painter = QPainter(result_pixmap)
        
        try:
            for screen_info in self.screens_info:
                screen_geometry = screen_info['geometry']
                
                screen_pixmap = app.primaryScreen().grabWindow(
                    0,
                    screen_geometry.x(),
                    screen_geometry.y(),
                    screen_geometry.width(),
                    screen_geometry.height()
                )
                
                if not screen_pixmap.isNull():
                    target_x = screen_geometry.x() - virtual_geometry.x()
                    target_y = screen_geometry.y() - virtual_geometry.y()
                    painter.drawPixmap(target_x, target_y, screen_pixmap)
        finally:
            painter.end()
        
        return result_pixmap
    
    def show_overlays(self):
        """显示所有覆盖层"""
        for overlay in self.screen_overlays:
            overlay.show()
            overlay.raise_()
            overlay.activateWindow()
    
    def hide_overlays(self):
        """隐藏所有覆盖层"""
        for overlay in self.screen_overlays:
            overlay.hide()
        self.rubber_band.hide()
    
    def on_selection_started(self, global_pos, screen_index):
        """选择开始"""
        # print(f"在屏幕 {screen_index} 开始选择: ({global_pos.x()}, {global_pos.y()})")
        self.rubber_band.setGeometry(QRect(global_pos, QSize()))
        self.rubber_band.show()
        self.rubber_band.raise_()
    
    def on_selection_updated(self, rect, screen_index):
        """选择更新"""
        self.rubber_band.setGeometry(rect)
    
    def on_selection_finished(self, rect, screen_index):
        """选择完成"""
        # print(f"在屏幕 {screen_index} 完成选择: {rect.width()}x{rect.height()} at ({rect.x()}, {rect.y()})")
        
        self.hide_overlays()
        
        # 转换为相对于虚拟桌面的坐标
        virtual_geometry = self.virtual_desktop_geometry
        relative_rect = QRect(
            rect.x() - virtual_geometry.x(),
            rect.y() - virtual_geometry.y(),
            rect.width(),
            rect.height()
        )
        
        # 确保坐标在有效范围内
        full_rect = QRect(0, 0, self.full_screenshot.width(), self.full_screenshot.height())
        clipped_rect = relative_rect.intersected(full_rect)
        
        if not self.full_screenshot.isNull() and not clipped_rect.isEmpty():
            cropped = self.full_screenshot.copy(clipped_rect)
            self.screenshot_taken.emit(cropped)
        else:
            # print("截图区域无效")
            self.screenshot_cancelled.emit()
    
    def on_selection_cancelled(self):
        """选择取消"""
        # print("截图取消")
        self.hide_overlays()
        self.screenshot_cancelled.emit()
    
    def start_capture(self):
        """开始截图"""
        self.show_overlays()

class QuickScreenshot:
    """快速截图工具类"""
    def __init__(self, save_directory=None):
        self.capture_widget = None
        self.result_pixmap = None
        self.is_cancelled = False
        self.save_directory = save_directory or os.getcwd()  # 默认保存到当前目录
        
    def _generate_filename(self, prefix="screenshot"):
        """生成带时间戳的文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.png"
    
    def _save_screenshot(self, pixmap, filename=None):
        """保存截图并返回保存路径"""
        if pixmap is None or pixmap.isNull():
            return None
            
        if filename is None:
            filename = self._generate_filename()
        
        # 确保保存目录存在
        os.makedirs(self.save_directory, exist_ok=True)
        
        save_path = os.path.join(self.save_directory, filename)
        
        try:
            success = pixmap.save(save_path)
            if success:
                return os.path.abspath(save_path)
            else:
                return None
        except Exception as e:
            print(f"保存截图失败: {e}")
            return None
        
    def take_area_screenshot(self):
        """进行区域截图，返回(pixmap, save_path)"""
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        
        self.result_pixmap = None
        self.is_cancelled = False
        
        # 使用新的多屏幕捕获器
        self.capture_widget = MultiScreenCapture()
        self.capture_widget.screenshot_taken.connect(self._on_screenshot_taken)
        self.capture_widget.screenshot_cancelled.connect(self._on_screenshot_cancelled)
        
        # 开始捕获
        self.capture_widget.start_capture()
        
        # 等待用户操作
        while (self.capture_widget and 
               len([overlay for overlay in self.capture_widget.screen_overlays if overlay.isVisible()]) > 0):
            app.processEvents()
            time.sleep(0.01)
        
        if self.is_cancelled or self.result_pixmap is None:
            return None, None
        
        # 保存截图
        save_path = self._save_screenshot(self.result_pixmap, self._generate_filename("area_screenshot"))
        
        return self.result_pixmap, save_path
    
    def take_full_screenshot(self):
        """进行全屏截图（所有屏幕），返回(pixmap, save_path)"""
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        
        temp_capture = MultiScreenCapture()
        full_screenshot = temp_capture.capture_all_screens()
        temp_capture.deleteLater()
        
        if full_screenshot is None or full_screenshot.isNull():
            return None, None
        
        # 保存截图
        save_path = self._save_screenshot(full_screenshot, self._generate_filename("full_screenshot"))
        
        return full_screenshot, save_path
    
    def _on_screenshot_taken(self, pixmap):
        """截图完成回调"""
        self.result_pixmap = pixmap
        self.is_cancelled = False
    
    def _on_screenshot_cancelled(self):
        """截图取消回调"""
        self.is_cancelled = True

# 便捷函数
def take_area_screenshot(save_directory=None):
    """便捷的区域截图函数，返回(pixmap, save_path)"""
    screenshot_tool = QuickScreenshot(save_directory)
    return screenshot_tool.take_area_screenshot()

def take_full_screenshot(save_directory=None):
    """便捷的全屏截图函数（所有屏幕），返回(pixmap, save_path)"""
    screenshot_tool = QuickScreenshot(save_directory)
    return screenshot_tool.take_full_screenshot()

def list_screens():
    """列出所有屏幕信息"""
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    desktop = QDesktopWidget()
    # print(f"检测到 {desktop.screenCount()} 个屏幕:")
    
    for i in range(desktop.screenCount()):
        geometry = desktop.screenGeometry(i)
        available = desktop.availableGeometry(i)
        is_primary = (i == desktop.primaryScreen())
        
        # print(f"屏幕 {i}{'(主屏)' if is_primary else ''}:")
        # print(f"  全尺寸: {geometry.width()}x{geometry.height()} at ({geometry.x()}, {geometry.y()})")
        # print(f"  可用区域: {available.width()}x{available.height()} at ({available.x()}, {available.y()})")

# 测试代码
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 显示屏幕信息
    list_screens()
    
    # print("\n多屏幕截图测试")
    # print("现在可以在任意屏幕上进行截图选择！")
    # print("按 ESC 键取消截图")
    
    # print("\n开始多屏幕区域截图...")
    pixmap, save_path = take_area_screenshot()
    
    if pixmap and save_path:
        print(f"截图成功！尺寸: {pixmap.width()}x{pixmap.height()}")
        print(f"截图已保存到: {save_path}")
    else:
        print("截图取消或失败")
    
    sys.exit()