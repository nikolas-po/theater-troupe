"""
Модуль управления темами приложения.
"""
import wx
import wx.grid as gridlib
import logging


class ThemeManager:
    """Singleton управляющий цветовой схемой приложения и синхронизацией с ОС."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self._current_theme = 'light'

        self.light_theme = {
            'bg': wx.Colour(255, 255, 255),
            'fg': wx.Colour(0, 0, 0),
            'panel_bg': wx.Colour(245, 245, 245),
            'button_bg': wx.Colour(240, 240, 240),
            'button_fg': wx.Colour(0, 0, 0),
            'text_ctrl_bg': wx.Colour(255, 255, 255),
            'text_ctrl_fg': wx.Colour(0, 0, 0),
            'listbox_bg': wx.Colour(255, 255, 255),
            'listbox_fg': wx.Colour(0, 0, 0),
            'grid_bg': wx.Colour(255, 255, 255),
            'grid_fg': wx.Colour(0, 0, 0),
            'header_bg': wx.Colour(230, 230, 230),
            'header_fg': wx.Colour(0, 0, 0),
            'grid_selection_bg': wx.Colour(200, 220, 255),
            'grid_selection_fg': wx.Colour(0, 0, 0),
        }
        
        self.dark_theme = {
            'bg': wx.Colour(30, 30, 30),
            'fg': wx.Colour(255, 255, 255),
            'panel_bg': wx.Colour(40, 40, 40),
            'button_bg': wx.Colour(50, 50, 50),
            'button_fg': wx.Colour(255, 255, 255),
            'text_ctrl_bg': wx.Colour(35, 35, 35),
            'text_ctrl_fg': wx.Colour(255, 255, 255),
            'listbox_bg': wx.Colour(35, 35, 35),
            'listbox_fg': wx.Colour(255, 255, 255),
            'grid_bg': wx.Colour(30, 30, 30),
            'grid_fg': wx.Colour(255, 255, 255),
            'header_bg': wx.Colour(50, 50, 50),
            'header_fg': wx.Colour(255, 255, 255),
            'grid_selection_bg': wx.Colour(70, 100, 150),
            'grid_selection_fg': wx.Colour(255, 255, 255),
        }
    
    def get_theme(self):
        return self.dark_theme if self._current_theme == 'dark' else self.light_theme
    
    def set_theme(self, theme_name, manual=False):
        """Устанавливает тему приложения.
        
        Args:
            theme_name (str): Название темы ('light' или 'dark').
            manual (bool): Флаг ручной установки (не используется, оставлен для совместимости).
            
        Returns:
            bool: True если тема успешно установлена, False в противном случае.
        """
        if theme_name in ('light', 'dark'):
            self._current_theme = theme_name
            return True
        return False
    
    def get_current_theme_name(self):
        return self._current_theme
    
    def apply_theme(self, window, force=False):
        theme = self.get_theme()
        try:
            if isinstance(window, (wx.Frame, wx.Dialog)):
                window.SetBackgroundColour(theme['bg'])
                window.SetOwnBackgroundColour(theme['bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, wx.Panel):
                window.SetBackgroundColour(theme['panel_bg'])
                window.SetOwnBackgroundColour(theme['panel_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, wx.Button):
                window.SetBackgroundColour(theme['button_bg'])
                window.SetForegroundColour(theme['button_fg'])
                window.SetOwnBackgroundColour(theme['button_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, wx.TextCtrl):
                window.SetBackgroundColour(theme['text_ctrl_bg'])
                window.SetForegroundColour(theme['text_ctrl_fg'])
                window.SetOwnBackgroundColour(theme['text_ctrl_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, (wx.ListBox, wx.CheckListBox)):
                window.SetBackgroundColour(theme['listbox_bg'])
                window.SetForegroundColour(theme['listbox_fg'])
                window.SetOwnBackgroundColour(theme['listbox_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, wx.StaticText):
                window.SetForegroundColour(theme['fg'])
                window.SetBackgroundColour(theme['panel_bg'])
                window.SetOwnBackgroundColour(theme['panel_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, wx.StaticBox):
                window.SetForegroundColour(theme['fg'])
                window.SetBackgroundColour(theme['panel_bg'])
                window.SetOwnBackgroundColour(theme['panel_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, wx.StatusBar):
                window.SetBackgroundColour(theme['panel_bg'])
                window.SetForegroundColour(theme['fg'])
                window.SetOwnBackgroundColour(theme['panel_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, wx.Notebook):
                window.SetBackgroundColour(theme['panel_bg'])
                window.SetOwnBackgroundColour(theme['panel_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, gridlib.Grid):
                window.SetDefaultCellBackgroundColour(theme['grid_bg'])
                window.SetDefaultCellTextColour(theme['grid_fg'])
                window.SetLabelBackgroundColour(theme['header_bg'])
                window.SetLabelTextColour(theme['header_fg'])
                window.SetBackgroundColour(theme['grid_bg'])
                window.SetOwnBackgroundColour(theme['grid_bg'])
                window.SetSelectionBackground(theme['grid_selection_bg'])
                window.SetSelectionForeground(theme['grid_selection_fg'])
                # Добавляем обводку для выделенных ячеек в темном стиле
                if self._current_theme == 'dark':
                    try:
                        # Увеличиваем ширину обводки для лучшей видимости
                        window.SetCellHighlightPenWidth(3)
                        window.SetCellHighlightROPenWidth(3)
                        # Устанавливаем яркий цвет обводки (яркий голубой)
                        highlight_pen = wx.Pen(wx.Colour(100, 200, 255), 3)
                        window.SetDefaultCellHighlightPen(highlight_pen)
                        window.SetDefaultCellHighlightROPen(highlight_pen)
                    except Exception as e:
                        logging.debug(f"Не удалось установить обводку для grid: {e}")
                window.SetThemeEnabled(False)
            elif isinstance(window, (wx.ComboBox, wx.Choice)):
                window.SetBackgroundColour(theme['text_ctrl_bg'])
                window.SetForegroundColour(theme['text_ctrl_fg'])
                window.SetOwnBackgroundColour(theme['text_ctrl_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, wx.CheckBox):
                window.SetBackgroundColour(theme['panel_bg'])
                window.SetForegroundColour(theme['fg'])
                window.SetOwnBackgroundColour(theme['panel_bg'])
                if hasattr(window, 'SetThemeEnabled'):
                    window.SetThemeEnabled(False)
            elif isinstance(window, wx.RadioBox):
                window.SetBackgroundColour(theme['panel_bg'])
                window.SetForegroundColour(theme['fg'])
                window.SetOwnBackgroundColour(theme['panel_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, wx.RadioButton):
                window.SetBackgroundColour(theme['panel_bg'])
                window.SetForegroundColour(theme['fg'])
                window.SetOwnBackgroundColour(theme['panel_bg'])
                if hasattr(window, 'SetThemeEnabled'):
                    window.SetThemeEnabled(False)
            elif isinstance(window, wx.MenuBar):
                window.SetBackgroundColour(theme['panel_bg'])
                window.SetForegroundColour(theme['fg'])
                window.SetOwnBackgroundColour(theme['panel_bg'])
                window.SetThemeEnabled(False)
            elif isinstance(window, wx.SearchCtrl):
                window.SetBackgroundColour(theme['text_ctrl_bg'])
                window.SetForegroundColour(theme['text_ctrl_fg'])
                window.SetOwnBackgroundColour(theme['text_ctrl_bg'])
                if hasattr(window, 'SetThemeEnabled'):
                    window.SetThemeEnabled(False)
            elif hasattr(window, '__class__'):
                class_name = window.__class__.__name__
                if any(marker in class_name for marker in ('TextCtrl', 'Combo', 'Date', 'Search')):
                    if hasattr(window, 'SetBackgroundColour'):
                        window.SetBackgroundColour(theme['text_ctrl_bg'])
                        window.SetOwnBackgroundColour(theme['text_ctrl_bg'])
                    if hasattr(window, 'SetForegroundColour'):
                        window.SetForegroundColour(theme['text_ctrl_fg'])
                    if hasattr(window, 'SetThemeEnabled'):
                        window.SetThemeEnabled(False)
        except Exception as e:
            logging.debug(f"Ошибка применения темы к {type(window).__name__}: {e}")
        
        try:
            window.Refresh()
            for child in window.GetChildren():
                self.apply_theme(child, force)
        except Exception as e:
            logging.debug(f"Ошибка применения темы к дочерним элементам: {e}")
    
    def apply_theme_to_all_windows(self):
        for window in wx.GetTopLevelWindows():
            if window:
                try:
                    self.apply_theme(window, force=True)
                    window.Refresh()
                    window.Update()
                except:
                    pass


# Singleton instance
theme_manager = ThemeManager()

