import urllib.request,urllib.error,json,pathlib,secrets,os,subprocess
BASE='http://127.0.0.1:30093';AUTH='MediaBrowser Client="Homelab", Device="pi5", DeviceId="homelab-bootstrap", Version="1.0"';token=None
def api(path,data=None,method=None):
 headers={'Authorization':AUTH+(', Token="'+token+'"' if token else ''),'Content-Type':'application/json'}
 req=urllib.request.Request(BASE+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
 try:
  with urllib.request.urlopen(req,timeout=40) as f:
   b=f.read();return json.loads(b) if b else None
 except urllib.error.HTTPError as e:raise RuntimeError('Jellyfin API HTTP '+str(e.code)+' at '+path.split('?')[0]) from None
assert os.geteuid()==0
private=pathlib.Path('/root/.config/homelab-jellyfin');private.mkdir(parents=True,exist_ok=True,mode=0o700);private.chmod(0o700)
cred=private/'initial-access.json'
if cred.exists():cfg=json.loads(cred.read_text())
else:
 cfg={'url':'https://jellyfin.bearsfamily.es','admin':{'username':'admin','password':secrets.token_urlsafe(18)},'family':{'username':'bearsfamily','password':secrets.token_urlsafe(18)}}
 oldmask=os.umask(0o077);cred.write_text(json.dumps(cfg,indent=2)+'\n');cred.chmod(0o600);os.umask(oldmask)
info=api('/System/Info/Public')
if not info.get('StartupWizardCompleted',False):
 api('/Startup/User')
 api('/Startup/User',{'Name':cfg['admin']['username'],'Password':cfg['admin']['password']},'POST')
 api('/Startup/Configuration',{'ServerName':'BearsFamily Cinema','UICulture':'es-ES','MetadataCountryCode':'ES','PreferredMetadataLanguage':'es'},'POST')
 api('/Startup/Complete',method='POST')
login=api('/Users/AuthenticateByName',{'Username':cfg['admin']['username'],'Pw':cfg['admin']['password']},'POST');token=login['AccessToken']
server=api('/System/Configuration');server.update({'ServerName':'BearsFamily Cinema','UICulture':'es-ES','MetadataCountryCode':'ES','PreferredMetadataLanguage':'es','QuickConnectAvailable':True});api('/System/Configuration',server,'POST')
net=api('/System/Configuration/network');net.update({'EnableUPnP':False,'AutoDiscovery':False,'KnownProxies':['127.0.0.1','192.168.1.163','10.244.0.1'],'LocalNetworkSubnets':['192.168.1.0/24','10.244.0.0/16','10.8.0.0/24'],'EnableRemoteAccess':False,'EnableHttps':False,'RequireHttps':False});api('/System/Configuration/network',net,'POST')
users=api('/Users');family=next((u for u in users if u['Name']==cfg['family']['username']),None)
if not family:family=api('/Users/New',{'Name':cfg['family']['username'],'Password':cfg['family']['password']},'POST')
policy=family['Policy'];policy.update({'IsAdministrator':False,'IsHidden':False,'EnableContentDeletion':False,'EnableVideoPlaybackTranscoding':False,'EnableAudioPlaybackTranscoding':True,'EnablePlaybackRemuxing':True,'EnableMediaConversion':False,'EnableSyncTranscoding':False,'EnableAllFolders':True,'EnableRemoteAccess':True,'EnablePublicSharing':False})
api('/Users/'+family['Id']+'/Policy',policy,'POST')
libraries=api('/Library/VirtualFolders')
if not any(l['Name']=='Películas' for l in libraries):
 opts={'Enabled':True,'PathInfos':[{'Path':'/media/movies'}],'EnableRealtimeMonitor':False,'PreferredMetadataLanguage':'es','MetadataCountryCode':'ES','SaveLocalMetadata':False,'SaveSubtitlesWithMedia':False,'EnableChapterImageExtraction':False,'ExtractChapterImagesDuringLibraryScan':False,'EnableTrickplayImageExtraction':False,'ExtractTrickplayImagesDuringLibraryScan':False,'EnableLUFSScan':False,'MetadataSavers':[],'DisabledSubtitleFetchers':['Open Subtitles'],'TypeOptions':[{'Type':'Movie','MetadataFetchers':['TheMovieDb'],'ImageFetchers':['TheMovieDb','Embedded Image Extractor','Screen Grabber'],'ImageOptions':[{'Type':'Primary','Limit':1,'MinWidth':0},{'Type':'Backdrop','Limit':1,'MinWidth':0}]}]}
 api('/Library/VirtualFolders?name=Pel%C3%ADculas&collectionType=movies&refreshLibrary=true',{'LibraryOptions':opts},'POST')
tasks=api('/ScheduledTasks');refresh=next(t for t in tasks if t.get('Key')=='RefreshLibrary')
api('/ScheduledTasks/'+refresh['Id']+'/Triggers',[{'Type':'IntervalTrigger','IntervalTicks':36000000000}], 'POST')
api('/Library/Refresh',method='POST')
summary={'server_version':info['Version'],'server_name':'BearsFamily Cinema','admin_username':cfg['admin']['username'],'playback_username':cfg['family']['username'],'movie_library':'/media/movies','read_only_media':True,'video_transcoding_for_family':False,'scan_interval_minutes':60,'credentials_file':str(cred),'quick_connect':True}
public=pathlib.Path('/var/lib/homelab-apps/jellyfin/public');public.mkdir(mode=0o755,exist_ok=True)
(public/'setup.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
