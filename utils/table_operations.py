from PyQt5.QtWidgets import QMenu, QAction
from PyQt5.QtCore import Qt


class TableOperationsMixin:
    """表格操作混入类"""
    
    def setup_table_context_menu(self, table):
        """为表格设置右键菜单"""
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(lambda pos: self.show_context_menu(pos, table))
        
        # 设置表格选择模式，允许多选
        table.setSelectionBehavior(table.SelectRows)  # 按行选择
        table.setSelectionMode(table.ExtendedSelection)  # 允许多选
    
    def show_context_menu(self, position, table):
        """显示右键菜单"""
        if table.itemAt(position) is not None:
            menu = QMenu()
            
            # 获取选中的行数
            selected_rows = self.get_selected_rows(table)
            
            if len(selected_rows) == 1:
                delete_action = QAction("删除此行", self)
            else:
                delete_action = QAction(f"删除选中的 {len(selected_rows)} 行", self)
            
            delete_action.triggered.connect(lambda: self.delete_selected_rows(table))
            menu.addAction(delete_action)
            
            # 在鼠标位置显示菜单
            menu.exec_(table.mapToGlobal(position))

    def get_selected_rows(self, table):
        """获取选中的行索引列表"""
        selected_rows = []
        for item in table.selectedItems():
            row = item.row()
            if row not in selected_rows:
                selected_rows.append(row)
        return sorted(selected_rows, reverse=True)  # 从大到小排序，这样删除时不会影响索引

    def delete_selected_rows(self, table):
        """删除选中的行"""
        selected_rows = self.get_selected_rows(table)
        
        if not selected_rows:
            return
        
        # 从大到小删除，避免索引变化的问题
        for row in selected_rows:
            table.removeRow(row)