"""
API для генерации и экспорта отчетов.
"""
import wx
import os
from datetime import datetime
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ReportExportDialog(wx.Dialog):
    """Диалог выбора формата и пути сохранения отчета"""
    
    def __init__(self, parent, report_name: str, default_formats: list = None):
        super().__init__(parent, title=f"Экспорт отчета: {report_name}", 
                        size=(750, 450))
        
        self.report_name = report_name
        self.selected_format = None
        self.selected_path = None
        self.default_formats = default_formats or ['PDF', 'XLSX']
        
        self._create_ui()
        self.Center()
    
    def _create_ui(self):
        """Создание интерфейса диалога"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Заголовок
        title = wx.StaticText(panel, label=f"Экспорт: {self.report_name}")
        title_font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL, 15)
        
        # Выбор формата
        format_box = wx.StaticBox(panel, label="Формат отчета")
        format_sizer = wx.StaticBoxSizer(format_box, wx.VERTICAL)
        
        format_label = wx.StaticText(panel, label="Выберите формат:")
        format_sizer.Add(format_label, 0, wx.ALL, 5)
        
        self.format_choice = wx.RadioBox(
            panel,
            choices=self.default_formats,
            style=wx.RA_SPECIFY_COLS
        )
        self.format_choice.SetSelection(0)
        format_sizer.Add(self.format_choice, 0, wx.ALL | wx.EXPAND, 5)
        
        main_sizer.Add(format_sizer, 0, wx.ALL | wx.EXPAND, 10)
        
        # Выбор пути сохранения
        path_box = wx.StaticBox(panel, label="Путь сохранения")
        path_box_sizer = wx.StaticBoxSizer(path_box, wx.VERTICAL)
        
        path_label = wx.StaticText(panel, label="Файл будет сохранен по указанному пути:")
        path_box_sizer.Add(path_label, 0, wx.ALL, 5)
        
        path_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.path_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.path_text.SetMinSize((400, 60))
        path_sizer.Add(self.path_text, 1, wx.ALL | wx.EXPAND, 5)
        
        browse_btn = wx.Button(panel, label="Обзор...")
        browse_btn.SetMinSize((100, -1))
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse)
        path_sizer.Add(browse_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        path_box_sizer.Add(path_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        main_sizer.Add(path_box_sizer, 0, wx.ALL | wx.EXPAND, 10)
        
        # Кнопки
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "Сохранить")
        ok_btn.SetDefault()
        ok_btn.SetMinSize((100, -1))
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        cancel_btn.SetMinSize((100, -1))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        
        main_sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        
        panel.SetSizer(main_sizer)
        
        # Установка пути по умолчанию
        default_path = os.path.join(os.getcwd(), 'reports')
        if not os.path.exists(default_path):
            os.makedirs(default_path, exist_ok=True)
        self._update_default_path()
    
    def _update_default_path(self):
        """Обновление пути по умолчанию"""
        try:
            format_idx = self.format_choice.GetSelection()
            if format_idx >= 0:
                format_ext = self.default_formats[format_idx].lower()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_filename = f"{self.report_name}_{timestamp}.{format_ext}"
                default_path = os.path.join(os.getcwd(), 'reports', default_filename)
                self.path_text.SetValue(default_path)
        except Exception as e:
            logging.error(f"Ошибка обновления пути: {e}")
    
    def _on_browse(self, event):
        """Обработчик кнопки обзора"""
        format_ext = self.default_formats[self.format_choice.GetSelection()].lower()
        wildcard = f"*.{format_ext}|*.{format_ext}"
        
        if format_ext == 'pdf':
            wildcard = "PDF файлы (*.pdf)|*.pdf"
        elif format_ext == 'xlsx':
            wildcard = "Excel файлы (*.xlsx)|*.xlsx"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{self.report_name}_{timestamp}.{format_ext}"
        
        with wx.FileDialog(
            self,
            "Сохранить отчет как",
            defaultDir=os.path.join(os.getcwd(), 'reports'),
            defaultFile=default_filename,
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            path = file_dialog.GetPath()
            self.path_text.SetValue(path)
    
    def GetValues(self) -> Tuple[Optional[str], Optional[str]]:
        """Возвращает выбранный формат и путь"""
        if self.ShowModal() == wx.ID_OK:
            format_idx = self.format_choice.GetSelection()
            selected_format = self.default_formats[format_idx] if format_idx >= 0 else None
            selected_path = self.path_text.GetValue().strip()
            
            # Убираем переносы строк из пути
            if selected_path:
                selected_path = selected_path.replace('\n', '').replace('\r', '')
            
            if selected_path and selected_format:
                # Проверяем, что путь валидный
                try:
                    # Создаем директорию если её нет
                    dir_path = os.path.dirname(selected_path)
                    if dir_path and not os.path.exists(dir_path):
                        os.makedirs(dir_path, exist_ok=True)
                    return selected_format, selected_path
                except Exception as e:
                    logger.error(f"Ошибка валидации пути: {e}")
                    return None, None
        
        return None, None


def show_export_dialog(parent, report_name: str, formats: list = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Показывает диалог выбора формата и пути экспорта.
    
    Args:
        parent: Родительское окно
        report_name: Название отчета
        formats: Список доступных форматов (по умолчанию ['PDF', 'XLSX'])
    
    Returns:
        Tuple[format, path] или (None, None) если отменено
    """
    dialog = ReportExportDialog(parent, report_name, formats or ['PDF', 'XLSX'])
    result = dialog.GetValues()
    dialog.Destroy()
    return result

