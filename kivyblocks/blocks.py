import os
import sys
import codecs
import json
from traceback import print_exc

import kivy
from functools import partial

from appPublic.dictExt import dictExtend
from appPublic.folderUtils import ProgramPath
from appPublic.dictObject import DictObject
from appPublic.Singleton import SingletonDecorator, GlobalEnv
from appPublic.datamapping import keyMapping
from appPublic.registerfunction import RegisterFunction

from kivy.logger import Logger
from kivy.config import Config
from kivy.metrics import sp,dp,mm
from kivy.core.window import WindowBase, Window
from kivy.properties import BooleanProperty
from kivy.uix.widget import Widget
from kivy.app import App
from kivy.factory import Factory
from kivy.uix.video import Video
from .baseWidget import *
from .toolbar import *
from .dg import DataGrid
from .utils import *
from .serverImageViewer import ServerImageViewer
from .vplayer import VPlayer
from .form import InputBox, Form, StrSearchForm
from .boxViewer import BoxViewer
from .tree import Tree, TextTree
from .newvideo import Video
from .ready import WidgetReady
from .bgcolorbehavior import BGColorBehavior
from .orientationlayout import OrientationLayout
from .threadcall import HttpClient
from .register import *

def showError(e):
	print('error',e)


def wrap_ready(klass):
	try:
		w = Factory.get(klass)
		if hasattr(w,'ready'):
			return w
		Factory.unregister(klass)
		globals()[klass] = w
	except:
		w = globals().get(klass)
		if w is None:
			return None
		if hasattr(w,'ready'):
			return w
		
	script = f"""class R_{klass}(WidgetReady, {klass}):
	def __init__(self, **kw):
		{klass}.__init__(self, **kw)
		WidgetReady.__init__(self)
""" 
	exec(script,globals(),globals())
	newWidget = globals().get(f'R_{klass}')
	Factory.register(klass,newWidget)
	return newWidget

class WidgetNotFoundById(Exception):
	def __init__(self, id):
		super().__init__()
		self.idstr = id
	
	def __str__(self):
		return "Widget not found by id:" + self.idstr + ':'

	def __expr__(self):
		return str(self)

class ClassMethodNotFound(Exception):
	def __init__(self,k,m):
		super().__init__()
		self.kname = k
		self.mname = m

	def __str__(self):
		s = 'Method(%s) not found in class(%s)' % (self.mname,
					str(self.kname.__classname__))
		return s
	
	def __expr__(self):
		return self.__str__()

	
class NotExistsObject(Exception):
	def __init__(self,name):
		super().__init__()
		self.name = name

	def __str__(self):
		s = 'not exists widget(%s)' % self.name
		return s
	
	def __expr__(self):
		return self.__str__()

class ArgumentError(Exception):
	def __init__(self,argument,desc):
		super().__init__()
		self.argument = argument
		self.desc = desc
	
	def __str__(self):
		s = 'argument(%s) missed:%s' % (self.argument,self.desc)
		return s
	
	def __expr__(self):
		return self.__str__()


class NotRegistedWidget(Exception):
	def __init__(self,name):
		super().__init__()
		self.widget_name = name

	def __str__(self):
		s = 'not reigsted widget(%s)' % self.name
		return s
	
	def __expr__(self):
		return self.__str__()

def registerWidget(name,widget):
	globals()[name] = widget


class Blocks(EventDispatcher):
	def __init__(self):
		EventDispatcher.__init__(self)
		self.action_id = 0
		self.register_event_type('on_built')
		self.register_event_type('on_failed')
		self.env = GlobalEnv()

	def set(self,k,v):
		self.env[k] = v
	
	def register_widget(self,name,widget):
		globals()[name] = widget

	def buildAction(self,widget,desc):
		conform_desc = desc.get('conform')
		blocks = Blocks()
		if not conform_desc:
			return partial(blocks.uniaction, widget, desc)
		l = {
		}
		body="""def action(widget, *args, **kw):
	jsonstr='''%s'''
	desc = json.loads(jsonstr)
	conform_desc = desc.get('conform')
	blocks = Blocks()
	if not conform_desc:
		blocks.uniaction(widget, desc,*args, **kw)
		return
	w = blocks.widgetBuild({
		"widgettype":"Conform",
		"options":conform_desc
	})
	w.bind(on_conform=partial(blocks.uniaction, widget, desc))
	w.open()
	print('Conform show.....')
""" % (json.dumps(desc))
		exec(body,globals(),l)
		f = l.get('action',None)
		if f is None:
			raise Exception('None Function')
		func =partial(f,widget)
		return func
		
	def eval(self,s,l):
		g = {}
		forbidens = [
			"os",
			"sys",
			"codecs",
			"json",
		]

		for k,v in globals().copy().items():
			if k not in forbidens:
				g[k] = v

		g['__builtins__'] = globals()['__builtins__'].copy()
		g['__builtins__']['__import__'] = None
		g['__builtins__']['__loader__'] = None
		g['__builtins__']['open'] = None
		g.update(self.env)
		return eval(s,g,l)

	def getUrlData(self,url,method='GET',params={}, files={},
					callback=None,
					errback=None,**kw):

		if url is None:
			if errback:
				errback(None,Exception('url is None'))
			else:
				return None

		if url.startswith('file://'):
			filename = url[7:]
			with codecs.open(filename,'r','utf-8') as f:
				b = f.read()
				dic = json.loads(b)
				return dic
		elif url.startswith('http://') or url.startswith('https://'):
			try:
				hc = HttpClient()
				resp=hc(url,method=method,params=params,files=files)
				# print('Blocks.py :resp=',resp)
				return resp
			except Exception as e:
				if errback:
					return errback(None,e)
				return None
		else:
			config = getConfig()
			url = config.uihome + url
			return self.getUrlData(url,method=method,
					params=params,
					files=files,
					**kw)

	def strValueExpr(self,s:str,localnamespace:dict={}):
		if not s.startswith('py::'):
			return s
		s = s[4:]
		try:
			v = self.eval(s,localnamespace)
			return v
		except Exception as e:
			print('Exception .... ',e,'script=',s)
			print_exc()
			return s

	def arrayValueExpr(self,arr:list,localnamespace:dict={}):
		d = []
		for v in arr:
			if type(v) == type(''):
				d.append(self.strValueExpr(v,localnamespace))
				continue
			if type(v) == type([]):
				d.append(self.arrayValueExpr(v,localnamespace))
				continue
			if type(v) == type({}):
				d.append(self.dictValueExpr(v,localnamespace))
				continue
			if type(v) == type(DictObject):
				d.append(self.dictValueExpr(v,localnamespace))
				continue
			d.append(v)
		return d

	def dictValueExpr(self,dic:dict,localnamespace:dict={}):
		d = {}
		for k,v in dic.items():
			if type(v) == type(''):
				d[k] = self.strValueExpr(v,localnamespace)
				continue
			if type(v) == type([]):
				d[k] = self.arrayValueExpr(v,localnamespace)
				continue
			if type(v) == type({}):
				d[k] = self.dictValueExpr(v,localnamespace)
				continue
			if type(v) == type(DictObject):
				d[k] = self.dictValueExpr(v,localnamespace)
				continue
			d[k] = v
		return d
	def valueExpr(self,obj,localnamespace={}):
		if type(obj) == type(''):
			return self.strValueExpr(obj,localnamespace)
		if type(obj) == type([]):
			return self.arrayValueExpr(obj,localnamespace)
		if type(obj) == type({}):
			return self.dictValueExpr(obj,localnamespace)
		if isinstance(obj,DictObject):
			return self.dictValueExpr(obj,localnamespace)
		return obj

	def w_build(self,desc:dict):
		# print('w_build(),desc=',desc)
		widgetClass = desc.get('widgettype',None)
		if not widgetClass:
			Logger.info("Block: w_build(), desc invalid", desc)
			raise Exception(desc)

		widgetClass = desc['widgettype']
		opts = self.valueExpr(desc.get('options',{}).copy())
		widget = None
		try:
			klass = wrap_ready(widgetClass)
			widget = klass(**opts)
		except Exception as e:
			print('Error:',widgetClass,'not registered')
			print_exc()
			raise NotExistsObject(widgetClass)

		if desc.get('id'):
			widget.widget_id = desc.get('id')
		
		widget.build_desc = desc
		self.build_attributes(widget,desc)
		self.build_rest(widget,desc)
		return widget
		
	def build_attributes(self,widget,desc,t=None):
		excludes = ['widgettype','options','subwidgets','binds']
		for k,v in [(k,v) for k,v in desc.items() if k not in excludes]:
			if isinstance(v,dict) and v.get('widgettype'):
				b = Blocks()
				w = b.w_build(v)
				if hasattr(widget,k):
					aw = getattr(widget,k)
					if isinstance(aw,Layout):
						aw.add_widget(w)
						continue
				setattr(widget,k,w)
				continue
			setattr(widget,k,self.valueExpr(v,\
						localnamespace={'self':widget}))

	def build_rest(self, widget,desc,t=None):
		self.subwidget_total = len(desc.get('subwidgets',[]))
		self.subwidgets = [ None for i in range(self.subwidget_total)]
		pos = 0
		for pos,sw in enumerate(desc.get('subwidgets',[])):
			b = Blocks()
			kw = sw.copy()
			w = b.widgetBuild(kw)
			widget.add_widget(w)

		for b in desc.get('binds',[]):
			kw = self.valueExpr(b.copy(), \
						localnamespace={'self':widget})
			self.buildBind(widget,kw)

	def buildBind(self,widget,desc):
		wid = desc.get('wid','self')
		w = Blocks.getWidgetById(desc.get('wid','self'),from_widget=widget)
		if not w:
			Logger.info('Block: %s %s',desc.get('wid','self'),
							'not found via Blocks.getWidgetById()')
			return
		event = desc.get('event')
		if event is None:
			Logger.info('Block: binds desc miss event, desc=%s',str(desc))
			return
		f = self.buildAction(widget,desc)
		if f is None:
			Logger.info('Block: get a null function,%s',str(desc))
			return
		w.bind(**{event:f})
		# Logger.info('Block: %s bind built', str(desc))
	
	def multipleAction(self, widget, desc, *args):
		mydesc = {
			'wid':desc['wid'],
			'event':desc['event']
		}
		for a in desc['actions']:
			new_desc = mydesc.copy()
			new_desc.update(a)
			self.unication(widget,new_desc, **args)

	def uniaction(self,widget,desc, *args):
		Logger.info('Block: uniaction() called, desc=%s', str(desc))
			
		acttype = desc.get('actiontype')
		if acttype=='blocks':
			return self.blocksAction(widget,desc, *args)
		if acttype=='urlwidget':
			return self.urlwidgetAction(widget,desc, *args)
		if acttype == 'registedfunction':
			return self.registedfunctionAction(widget,desc, *args)
		if acttype == 'script':
			return self.scriptAction(widget, desc, *args)
		if acttype == 'method':
			return self.methodAction(widget, desc, *args)
		if acttype == 'event':
			return self.eventAction(widget, desc, *args)
		if acttype == 'multiple':
			return self.MultipleAction(widget, desc, *args)

		alert("actiontype(%s) invalid" % acttype,title='error')

	def eventAction(self, widget, desc, *args):
		target = Blocks.getWidgetById(desc.get('target','self'),widget)
		event = desc.get('dispatch_event')
		if not event:
			Logger.info('Block: eventAction():desc(%s) miss dispatch_event',
							str(desc))
			return
		params = desc.get('params',{})
		d = self.getActionData(widget,desc)
		if d:
			params.update(d)
		try:
			target.dispatch(event, **params)
		except Exception as e:
			Logger.info(f'Block: eventAction():dispatch {event} error')
			return
			
	def blocksAction(self,widget,desc, *args):
		target = Blocks.getWidgetById(desc.get('target','self'),widget)
		if target is None:
			Logger.info('Block: blocksAction():desc(%s) target not found',
							str(desc))
			return
		add_mode = desc.get('mode','replace')
		opts = desc.get('options').copy()
		d = self.getActionData(widget,desc)
		p = opts.get('options',{}).copy()
		if d:
			p.update(d)
		opts['options'] = p
		def doit(target,add_mode,o,w):
			if add_mode == 'replace':
				target.clear_widgets()
			target.add_widget(w)

		def doerr(o,e):
			Logger.info('Block: blocksAction(): desc=%s widgetBuild error'
								,str(desc))
			raise e

		b = Blocks()
		b.bind(on_built=partial(doit,target,add_mode))
		b.bind(on_failed=doerr)
		b.widgetBuild(opts)
		
	def urlwidgetAction(self,widget,desc, *args):
		target = Blocks.getWidgetById(desc.get('target','self'),widget)
		if target is None:
			Logger.info('Block: urlwidgetAction():desc(%s) target not found',
							str(desc))
			return
		add_mode = desc.get('mode','replace')
		opts = desc.get('options').copy()
		p = opts.get('params',{}).copy()
		if len(args) >= 1 and isinstance(args[0],dict):
			p.update(args[0])
		d = self.getActionData(widget,desc)
		if d:
			p.update(d)
		opts['params'] = p
		d = {
			'widgettype' : 'urlwidget',
			'options': opts
		}

		def doit(target,add_mode,o,w):
			if add_mode == 'replace':
				target.clear_widgets()
			target.add_widget(w)

		def doerr(o,e):
			Logger.info('Block: urlwidgetAction(): desc=%s widgetBuild error'
								,str(desc))

		b = Blocks()
		b.bind(on_built=partial(doit,target,add_mode))
		b.bind(on_failed=doerr)
		b.widgetBuild(d)
			
	def getActionData(self,widget,desc,*args):
		data = {}
		if desc.get('datawidget',False):
			dwidget = Blocks.getWidgetById(desc.get('datawidget','self'),
							from_widget=widget)
			if dwidget is None:
				Logger.info('Block: desc(%s) datawidget not defined',
							str(desc))
			if hasattr(dwidget,'getValue'):
				data = dwidget.getValue()
				if desc.get('keymapping'):
					data = keyMapping(data, desc.get('keymapping'))
			else:
				Logger.info('Block: desc(%s) datawidget has not getValue',
							str(desc))
		return data

	def registedfunctionAction(self, widget, desc, *args):
		target = Blocks.getWidgetById(desc.get('target','self'),
							from_widget=widget)
		if target is None:
			Logger.info('Block: registedfunctionAction():desc(%s) target not found',
							str(desc))
			return
		rf = RegisterFunction()
		name = desc.get('rfname')
		func = rf.get(name)
		if func is None:
			Logger.info('Block: desc=%s rfname(%s) not found', 
						str(desc), name)
			raise Exception('rfname(%s) not found' % name)

		params = desc.get('params',{}).copy()
		d = self.getActionData(widget,desc)
		if d:
			params.update(d)
		func(target, *args, **params)

	def scriptAction(self, widget, desc, *args):
		script = desc.get('script')
		if not script:
			Logger.info('Block: scriptAction():desc(%s) target not found',
							str(desc))
			return 
		target = Blocks.getWidgetById(desc.get('target','self'),
						from_widget=widget)
		if target is None:
			Logger.info('Block: scriptAction():desc(%s) target not found',
							str(desc))
		d = self.getActionData(widget,desc)
		ns = {
			"self":target,
			"args":args
		}
		if d:
			ns.update(d)
		try:
			self.eval(script, ns)
		except Exception as e:
			print_exc()
			print(e)
	
	def methodAction(self, widget, desc, *args):
		method = desc.get('method')
		target = Blocks.getWidgetById(desc.get('target','self'),widget)
		if target is None:
			Logger.info('Block: methodAction():desc(%s) target not found',
							str(desc))
			return
		if hasattr(target,method):
			f = getattr(target, method)
			kwargs = desc.get('options',{}).copy()
			d = self.getActionData(widget,desc)
			if d:
				kwargs.update(d)
			f(*args, **kwargs)
		else:
			alert('%s method not found' % method)

	def widgetBuild(self,desc):
		"""
		desc format:
		{
			widgettype:<registered widget>,
			id:widget id,
			options:{}
			subwidgets:[
			]
			binds:[
			]
		}
		"""
		def doit(desc):
			if not isinstance(desc,dict):
				Logger.info('Block: desc must be a dict object',
							desc,type(desc))
				return None

			# desc = self.valueExpr(desc)
			try:
				widget = self.w_build(desc)
				self.dispatch('on_built',widget)
				if hasattr(widget,'ready'):
					widget.ready()
				return widget
			except Exception as e:
				self.dispatch('on_failed',e)
				return None

		if not (isinstance(desc, DictObject) or isinstance(desc, dict)):
			print('Block: desc must be a dict object',
						desc,type(desc))
			self.dispatch('on_failed',Exception('miss url'))
			return

		widgettype = desc.get('widgettype')
		while widgettype == "urlwidget":
			opts = desc.get('options',{}).copy()
			extend = desc.get('extend')
			addon = None
			if desc.get('extend'):
				addon = desc.get('extend').copy()
			url = opts.get('url')
			if url is None:
				self.dispatch('on_failed',Exception('miss url'))
				return
			
			if opts.get('url'):
				del opts['url']
			desc = self.getUrlData(url,**opts)
			if not (isinstance(desc, DictObject) or \
							isinstance(desc, dict)):
				print('Block: desc must be a dict object',
								desc,type(desc))
				self.dispatch('on_failed',Exception('miss url'))
				return

			if addon:
				desc = dictExtend(desc,addon)
			widgettype = desc.get('widgettype')
		if widgettype is None:
			print('Block: desc must be a dict object',
						desc,type(desc))
			return None
		return doit(desc)
	
	@classmethod
	def getWidgetById(self,id,from_widget=None):
		def find_widget_by_id(id, from_widget):
			if id=='self':
				return from_widget
			if hasattr(from_widget,'widget_id'):
				if from_widget.widget_id == id:
					return from_widget
			if hasattr(from_widget, id):
				w = getattr(from_widget,id)
				if isinstance(w,Widget):
					return w
			for c in from_widget.children:
				ret = find_widget_by_id(id,from_widget=c)
				if ret:
					return ret
			app = App.get_running_app()
			if from_widget == app.root:
				if Window.fullscreen == True:
					w = app.fs_widget
					if w:
						return find_widget_by_id(id, w)
			return None
		ids = id.split('.')
		app = App.get_running_app()
		if id.startswith('/self') or id.startswith('root'):
			from_widget = app.root
			ids[0] = 'self'
		if from_widget is None:
			from_widget = app.root
		for id in ids:
			w = find_widget_by_id(id,from_widget=from_widget)
			if w is None:
				return None
			from_widget = w
		return w

	def on_built(self,v=None):
		return

	def on_failed(self,e=None):
		return

Factory.register('Blocks',Blocks)
Factory.register('Video',Video)
Factory.register('OrientationLayout', OrientationLayout)
