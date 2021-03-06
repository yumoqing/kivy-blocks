from kivy.event import EventDispatcher
from kivy.core.window import Window
from kivy.utils import platform
from kivy.app import App
from kivy.properties import BooleanProperty

desktopOSs=[
	"win",
	"linux",
	"macosx"
]

class WidgetReady(EventDispatcher):
	fullscreen = BooleanProperty(False)
	_fullscreen_state = False

	def __init__(self):
		self.register_event_type('on_ready')
		self._ready = False

	def on_ready(self):
		pass

	def ready(self):
		if self._ready:
			return
		self.dispatch('on_ready')
		self._ready = True

	def reready(self):
		self._ready = False
		self.ready()

	def use_keyboard(self):
		self.my_kb = Window.request_keyboard(None, self)
		if not self.my_kb:
			print('my_kb is None........')
			return 
		self.my_kb.bind(on_key_down=self._on_keyboard_down)
		if self.my_kb.widget:
			self.my_kb.set_mode_free()

	def key_handle(self,keyinfo):
		pass

	def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
		print('The key', keycode, 'have been pressed')
		print(' - text is %r' % text)
		print(' - modifiers are %r' % modifiers)
		keyinfo = {
			"keyname":keycode[1],
			"modifiers":modifiers
		}
		self.key_handle(keyinfo)
		return True

	def on_fullscreen(self, instance, value):
		window = self.get_parent_window()
		if not window:
			Logger.warning('VideoPlayer: Cannot switch to fullscreen, '
						   'window not found.')
			return
		if not self.parent:
			Logger.warning('VideoPlayer: Cannot switch to fullscreen, '
						   'no parent.')
			return

		app = App.get_running_app()
		if value:
			Window.fullscreen = True
			app.fs_widget = self
			self._fullscreen_state = state = {
				'parent': self.parent,
				'pos': self.pos,
				'size': self.size,
				'pos_hint': self.pos_hint,
				'size_hint': self.size_hint,
				'window_children': window.children[:]}

			# if platform in desktopOSs:
			# 	Window.maximize()
			# remove all window children
			for child in window.children[:]:
				window.remove_widget(child)

			# put the video in fullscreen
			if state['parent'] is not window:
				state['parent'].remove_widget(self)
			window.add_widget(self)

			# ensure the video widget is in 0, 0, and the size will be
			# readjusted
			self.pos = (0, 0)
			self.pos_hint = {}
			self.size_hint = (1, 1)
		else:
			app.fs_widget = None
			Window.fullscreen = False
			#if platform in desktopOSs:
			#	Window.restore()
			state = self._fullscreen_state
			window.remove_widget(self)
			for child in state['window_children']:
				window.add_widget(child)
			self.pos_hint = state['pos_hint']
			self.size_hint = state['size_hint']
			self.pos = state['pos']
			self.size = state['size']
			if state['parent'] is not window:
				state['parent'].add_widget(self)
