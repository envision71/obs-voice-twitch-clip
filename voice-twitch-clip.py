import os
import json
import csv
import datetime
import obspython as obs  # studio
from types import SimpleNamespace
from ctypes import *
import re
import requests

obsffi = CDLL("obs")
G = SimpleNamespace()
# Identifier of the hotkey set by OBS
HOTKEY_ID = obs.OBS_INVALID_HOTKEY_ID


# Description displayed in the Scripts dialog window
def script_description():
  return """<center><h2>Twitch Clip audio Trigger</h2></center>
            <p>Ever told your chat to clip something? Now you no longer need to tell them
            because you can create a clip by raising your voice or hotkey. You will need to
            give this script permision to create clips on your behalf.</p><p> 
            <a href="https://id.twitch.tv/oauth2/authorize?client_id=8f9alaqxdeycuabpicnecsvwafe3se&response_type=token&redirect_uri=http://localhost/&force_verify=true&scope=clips%3Aedit">Authorize with Twitch</a>
            and enter the website you get redirected to .</p>"""
            

# Callback for the hotkey
def on_clip_hotkey(pressed):
  G.is_pressed = pressed
  if G.is_pressed:
    print("hotkey was pressed")
    create_clip()


# Called at script load
def script_load(settings):
  global HOTKEY_ID
  #HOTKEY_ID = obs.obs_hotkey_register_frontend(script_path(), "Clip hotkey", on_clip_hotkey)
  hotkey_save_array = obs.obs_data_get_array(settings, "clip_hotkey")
  obs.obs_hotkey_load(HOTKEY_ID, hotkey_save_array)
  obs.obs_data_array_release(hotkey_save_array)

# Called before data settings are saved
def script_save(settings):
  # Hotkey save
  hotkey_save_array = obs.obs_hotkey_save(HOTKEY_ID)
  obs.obs_data_set_array(settings, "clip_hotkey", hotkey_save_array)
  obs.obs_data_array_release(hotkey_save_array)
  

# Called to set default values of data settings
def script_defaults(settings):
  obs.obs_data_set_default_string(settings, "source_name", "")
  obs.obs_data_set_default_double(settings, "db",-20)
  obs.obs_data_set_default_string(settings, "twitch_user", "")
  obs.obs_data_set_default_string(settings, "token_uri", "")



# Called to display the properties GUI
def script_properties():
  props = obs.obs_properties_create()
  #
  obs.obs_properties_add_text(props,"token_uri","Enter the redirect website",obs.OBS_TEXT_DEFAULT)
  #Twitch name
  obs.obs_properties_add_text(props,"twitch_user","Twitch username  to clip",obs.OBS_TEXT_DEFAULT)
  # Drop-down list of sources
  list_property = obs.obs_properties_add_list(props, "source_name", "Source name to listen to",
              obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
  populate_list_property_with_source_names(list_property)
  # Button to refresh the drop-down list
  obs.obs_properties_add_button(props, "button", "Refresh list of sources",
    lambda props,prop: True if populate_list_property_with_source_names(list_property) else True)  
  # User input for decibal to trigger at.
  obs.obs_properties_add_float_slider(props,"db","Decibal to trigger at",-100,0,0.5)
  return props

# Called after change of settings including once after script load
def script_update(settings):
  G.source_name = obs.obs_data_get_string(settings, "source_name")
  G.db = obs.obs_data_get_double(settings,"db")
  G.twitch_user = obs.obs_data_get_string(settings, "twitch_user")
  try:
    txt = obs.obs_data_get_string(settings, "token_uri")
    x= re.split("=",txt,1)
    y= re.split("&",x[1])
    G.token_uri = y[0]
    if validate_token(G.token_uri,settings):
      url = "https://api.twitch.tv/helix/users?"
      Params = {"login": G.twitch_user}
      Headers = {'Client-ID': "8f9alaqxdeycuabpicnecsvwafe3se", "Authorization":"Bearer "+G.token_uri}
      r = requests.get(url,params=Params,headers=Headers)
      G.user_id = (r.json()["data"][0]["id"])
    elif not validate_token(G.token_uri,settings):
      print("Token was not valid")
  except Exception as e:
    pass


def script_unload():
    g_obs_volmeter_remove_callback(G.volmeter, volmeter_callback, None)
    g_obs_volmeter_destroy(G.volmeter)
    obs.timer_remove(event_loop)
    obs.obs_hotkey_unregister(on_clip_hotkey)
    print("Removed volmeter & volmeter_callback")


#check of token is valid
def validate_token(token,settings):
  url = "https://id.twitch.tv/oauth2/validate"
  Headers = {'Authorization': 'OAuth '+token}
  r = requests.get(url,headers=Headers)
  if r.status_code == 200:
    return(True)
  elif r.status_code == 401:
    return(False)
  else:
    return(False)

    
# Fills the given list property object with the names of all sources plus an empty one
def populate_list_property_with_source_names(list_property):
  G.lock = False
  obs.timer_add(event_loop, G.tick)
  sources = obs.obs_enum_sources()
  obs.obs_property_list_clear(list_property)
  obs.obs_property_list_add_string(list_property, "", "")
  for source in sources:
    name = obs.obs_source_get_name(source)
    obs.obs_property_list_add_string(list_property, name, name)
  obs.source_list_release(sources)


def wrap(funcname, restype, argtypes):
    """Simplify wrapping ctypes functions in obsffi"""
    func = getattr(obsffi, funcname)
    func.restype = restype
    func.argtypes = argtypes
    globals()["g_" + funcname] = func


class Source(Structure):
    pass


class Volmeter(Structure):
    pass


volmeter_callback_t = CFUNCTYPE(
    None, c_void_p, POINTER(c_float), POINTER(c_float), POINTER(c_float)
)
wrap("obs_get_source_by_name", POINTER(Source), argtypes=[c_char_p])
wrap("obs_source_release", None, argtypes=[POINTER(Source)])
wrap("obs_volmeter_create", POINTER(Volmeter), argtypes=[c_int])
wrap("obs_volmeter_destroy", None, argtypes=[POINTER(Volmeter)])
wrap(
    "obs_volmeter_add_callback",
    None,
    argtypes=[POINTER(Volmeter), volmeter_callback_t, c_void_p],
)
wrap(
    "obs_volmeter_remove_callback",
    None,
    argtypes=[POINTER(Volmeter), volmeter_callback_t, c_void_p],
)
wrap(
    "obs_volmeter_attach_source",
    c_bool,
    argtypes=[POINTER(Volmeter), POINTER(Source)],
)


@volmeter_callback_t
def volmeter_callback(data, mag, peak, input):
    G.noise = float(peak[0])


#create a clip
def create_clip():
  contents = requests.get('https://www.twitch.tv/' + G.twitch_user).content.decode('utf-8')
  if 'isLiveBroadcast' in contents:
    print(G.twitch_user + ' is live')
    try:
      url = "https://api.twitch.tv/helix/clips?"
      Params = {"broadcaster_id": G.user_id}
      Headers = {'Client-ID': "8f9alaqxdeycuabpicnecsvwafe3se", "Authorization":"Bearer " + G.token_uri}
      r = requests.post(url,params=Params,headers=Headers)
      if r.status_code == 200:
        writer_file(r.json())
      elif r.status_code == 202:
        print(r.json())
        writer_file(r.json())
      elif r.status_code == 404:
        writer_file(r.json())
      elif r.status_code == 401:
        writer_file(r.json())
      else:
        pass
    except Exception as e:
        print("was not able to create clip")
        print(e)
        pass
  else:
    print(G.twitch_user + ' is not live')

def volume_check(volume):
  if not G.source_name == "":
    if volume < G.db:
      pass
    elif volume > G.db:
      create_clip()


def event_loop():
    """wait n seconds, then execute callback with db volume level within interval"""
    if G.duration > G.start_delay:
        #sceneitem = get_sceneitem_from_source_name_in_current_scene(G.source_name)
        if not G.lock:
            #print("setting volmeter")
            source = g_obs_get_source_by_name(G.source_name.encode("utf-8"))
            G.volmeter = g_obs_volmeter_create(OBS_FADER_LOG)
            g_obs_volmeter_add_callback(G.volmeter, volmeter_callback, None)
            if g_obs_volmeter_attach_source(G.volmeter, source):
                g_obs_source_release(source)
                G.lock = True
                print("Attached to source")
                return
        G.tick_acc += G.tick_mili
        

        if G.tick_acc > G.interval_sec:
            G.callback(G.noise)
            G.tick_acc = 0
    else:
        G.duration += G.tick_mili


def writer_file(content):
  content = content["data"][0]
  content["Date"] = str(datetime.date.today())
  print(content)
  if os.path.isfile(search):
    f = open(search,"a")
    csvwriter = csv.writer(f)
    csvwriter.writerow([content["Date"],content["id"],content["edit_url"]])
    print("wrote rows")
    f.close
  elif not os.path.isfile(search):
    print("File to write to is missing")



OBS_FADER_LOG = 2
G.is_pressed = False
G.file = "Clip_URLs.csv"
G.user_id = ""
G.token_uri = ""
G.twitch_user = ""
G.db = 0
G.lock = False
G.start_delay = 3
G.duration = 0
G.noise = 999
G.tick = 16
G.tick_mili = G.tick * 0.001
G.interval_sec = 0.5
G.tick_acc = 0
G.source_name = "Mic"
G.volmeter = "not yet initialized volmeter instance"
G.callback = volume_check

dir_path = os.path.dirname(os.path.realpath(__file__))
search = os.path.join(dir_path,G.file)
if os.path.isfile(search):
  pass
elif not os.path.isfile(search):
  f = open(search,"w")
  csvwriter = csv.DictWriter(f, fieldnames= ["Date","id","edit_url"])
  csvwriter.writeheader()
  f.close()