import os,threading
_started=False;_server=None;_lock=threading.Lock()
def start_server(home):
 global _started,_server
 with _lock:
  if _started:return True
  os.environ['JORDAN_AI_HOME']=home;os.environ['JORDAN_AI_PORT']='8765'
  import app
  app.init_db();app.STOP.clear();threading.Thread(target=app.worker,daemon=True).start();_server=app.Server((app.HOST,app.PORT),app.H);threading.Thread(target=_server.serve_forever,daemon=True).start();_started=True;return True
