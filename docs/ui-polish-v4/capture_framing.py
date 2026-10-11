import argparse, json, os, sys
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--source',required=True); p.add_argument('--output',required=True); p.add_argument('--backend',default='rust'); p.add_argument('--driver',default='dummy'); a=p.parse_args()
os.chdir(a.source);sys.path.insert(0,a.source);os.environ['HEADLESS']='0';os.environ['SDL_VIDEODRIVER']=a.driver
import pygame
from framework.engine import RMS
from framework.engine.renders import FRAME_CLEAR_COLOR
from framework.engine.game_engine import GameEngine
from rotk_env import components as c
from rotk_env.prefabs.config import GameConfig
from rotk_env.prefabs.world_builder import build_skirmish_world
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.session import NativeSession
from rotk_env.ui.context import VISUAL_VERSION
out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
e=GameEngine();GameConfig.sync_from_display();default=e.screen.get_size();records=[]
for size in (default,(1200,900),(2480,1263)):
 for scenario in ('default','river_split'):
  e.screen=pygame.display.set_mode(size,pygame.RESIZABLE);RMS.screen=e.screen;GameConfig.sync_from_display()
  opts=dict(display='window',scenario=scenario,seed=42,hub_url=None)
  session=NativeSession(authority_scheduling=False,**opts) if a.backend=='rust' else None
  w=session.world if session else build_skirmish_world(**opts);cam=w.get_singleton_component(c.Camera);ctx=w._ui_context
  before=session.runtime.export_state() if session else export_initial_state(w,display='window')
  for _ in range(10):
   e.screen.fill(FRAME_CLEAR_COLOR)
   if session: session.update_display(0,inputs=False)
   else:
    for s in w.systems:
     if type(s).__name__ in {'MapRenderSystem','UnitRenderSystem','EffectRenderSystem','PanelRenderSystem','UIRenderSystem','MiniMapSystem','UnitActionButtonSystem','UIButtonSystem'}:s.update(0)
   RMS.update()
  assert before==(session.runtime.export_state() if session else export_initial_state(w,display='window'))
  actual=e.screen.get_size();path=out/f'{scenario}-{actual[0]}x{actual[1]}.png';pygame.image.save(e.screen,path);pygame.display.flip()
  records.append(dict(requested_size=size,size=actual,scenario=scenario,viewport=list(ctx.layout.viewport),zoom=cam.zoom,offset=cam.get_offset(),authority_equal=True))
  if session:
   pixels=pygame.image.tobytes(e.screen,'RGB');_,err=session._capture_frame();assert not err;assert pixels==pygame.image.tobytes(e.screen,'RGB');session.close()
  else:ctx.close();w.reset()
(out/'result.json').write_text(json.dumps(dict(backend=a.backend,default_size=default,visual_version=VISUAL_VERSION,driver=pygame.display.get_driver(),captures=records),indent=2)+'\n');e.quit()
