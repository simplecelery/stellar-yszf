import time
import bs4
import requests
import StellarPlayer
import re
import urllib.parse
import urllib.request
import math
import json
import urllib3
import os
import sys
from shutil import copyfile
from datetime import datetime
import sqlite3

class yszfplugin(StellarPlayer.IStellarPlayerPlugin):
    def __init__(self,player:StellarPlayer.IStellarPlayer):
        super().__init__(player)
        urllib3.disable_warnings()
        self.dbconn = sqlite3.connect(':memory:', check_same_thread=False)
        self.medias = []
        self.allmovidesdata = {}
        self.mediaclass = []
        self.maxnum = 0
        self.pageindex = 1
        self.pagenumbers = 0
        self.apiurl = ''
        self.apitype = ''
        self.cur_page = ''
        self.max_page = ''
        self.pg = ''
        self.wd = ''
        self.ids = ''
        self.tid = ''
        self.daylist = True
        self.listday = 0
        self.listnum = 15
        self.actMedias = []
        self.dayarr = [{'title':'全部'},{'title':'周一'},{'title':'周二'},{'title':'周三'},{'title':'周四'},{'title':'周五'},{'title':'周六'},{'title':'周日'}]
        self.zfarr = [{'title':'追番列表'}]
        self.activeVision = '20211124193334'
        self.upvision = False

    
    def start(self):
        super().start()
        self.initdb()
        jsonpath = self.player.dataDirectory + '\\cartoon_source.json'
        if os.path.exists(jsonpath) == False:
            localpath = os.path.split(os.path.realpath(__file__))[0] + '\\cartoon_source.json'
            print(localpath)
            if os.path.exists(localpath):
                try:
                    copyfile(localpath,jsonpath)
                except IOError as e:
                    print("Unable to copy file. %s" % e)
                except:
                    print("Unexpected error:", sys.exc_info())
        self.downSource()
        self.loadSource()
        self.loadSelected()
        self.reloadDayList()
        self.pagenumbers = self.getPageNumbers()
        self.max_page = '共' + str(self.pagenumbers) + '页'
        self.cur_page = '第' + str(self.pageindex) + '页'
        if self.activeVision <= self.player.version:
            self.upvision = True
        
    def getPageNumbers(self):
        cur = self.dbconn.cursor()
        if self.daylist:
            cur.execute('select count(*) from flagmedialist')
        else:
            cur.execute('select count(*) from selected')
        allnumbers = cur.fetchone()[0]
        print('getPageNumbers:'+ str(allnumbers))
        num = allnumbers // self.listnum
        if allnumbers % self.listnum != 0:
            num = num + 1
        return num
            
    def getSourceOfDay(self,day):
        cur = self.dbconn.cursor()
        startnum = (self.pageindex  - 1) * self.listnum
        endmum = self.pageindex * self.listnum
        sqlstr = 'select id, name, detail, pic, 1 from selected '
        if self.daylist:
            sqlstr = 'select id, name, detail, pic, flag from flagmedialist '
            if day > 0:
                sqlstr = sqlstr + 'where day = ' + str(day)
        sqlstr = sqlstr + ' limit ' + str(startnum) + ',' + str(endmum)
        print(sqlstr)
        cur.execute(sqlstr)
        outarr = []
        for row in cur:
            newitem = {'id':row[0],'title':row[1],'info':row[2],'picture':row[3],'追番':str(row[4])}
            print(newitem)
            outarr.append(newitem)
        cur.close
        print(outarr)
        return outarr
    
    
    def initdb(self):
        cur = self.dbconn.cursor()
        cur.execute('create table medialist (id number,day number,name TEXT, detail TEXT,pic TEXT);')
        cur.execute('create table selected (id number,name TEXT,detail TEXT,pic TEXT,watched number);')
        cur.execute('create table lines (id number, url TEXT, decodetype TEXT, vid number);')
        cur.execute('create table mediaurls (id number, flag TEXT, title TEXT, url TEXT);')
        cur.execute('''create view flagmedialist as 
            select *,
            case when (select count(*) from selected where name = selected.name and name = medialist.name)>0 then 1 else 0 end as flag
            from medialist
            ''')
        self.dbconn.commit()
        cur.close()
    
    def stop(self):
        self.saveSelected()
        self.dbconn.close()
        super.stop()

    def downSource(self):
        down_url = "https://cdn.jsdelivr.net/gh/nomoodhalashao/my-movie@main/cartoon_source.json"
        try:
            r = requests.get(down_url,timeout = 5,verify=False) 
            result = r.status_code
            if result == 200:
                with open('cartoon_source.json','wb') as f:
                    f.write(r.content)
        except:
            print('get remote cartoon_source.json error')

        
    def loadSource(self):
        file = open('cartoon_source.json', "rb")
        fileJson = json.loads(file.read())
        n = 0
        ins = "insert or ignore INTO medialist(id, day, name, detail, pic) VALUES (?,?,?,?,?)"
        cur = self.dbconn.cursor()
        for item in fileJson:
            cur.execute(ins, (n,item['update_day'],item['name'],item['info'],item['picture']))
            lines = item['linelist']
            for line in lines:
                cur.execute('insert into lines (id,url,decodetype,vid) VALUES (?,?,?,?)', (n,line['apiurl'],line['apitype'],line['vid']))
            n = n + 1
        self.maxnum = n
        file.close()
        self.dbconn.commit()
        cur.close()

    def loadSelected(self):
        jsonpath = self.player.dataDirectory + '\\userselect.json'
        print(jsonpath)
        if os.path.exists(jsonpath) == False:
            return
        cur = self.dbconn.cursor()
        cur.execute('create table tmpselected (name TEXT,detail TEXT,pic TEXT,line TEXT,watched number);')
        self.dbconn.commit()
        file = open(jsonpath, "rb")
        fileJson = json.loads(file.read())
        ins = "INSERT INTO tmpselected(name, detail, pic, line, watched) VALUES (?,?,?,?,?)"
        for item in fileJson:
            print('loadSelected A:' + item['picture'])
            strlist = json.dumps(item['linelist'])
            cur.execute(ins, (item['name'],item['info'], item['picture'], strlist, item['actwatched']))
        file.close()
        self.dbconn.commit()
        cur.execute('select pic from tmpselected where name not in (select name from medialist)')
        print('flag1:' + str(cur.fetchall()))
        cur.execute('''insert into selected 
            (id, name, detail, pic, watched) 
            select medialist.id, tmpselected.name,tmpselected.detail, tmpselected.pic, tmpselected.watched 
            from tmpselected, medialist where tmpselected.name = medialist.name''')
        self.dbconn.commit()
        cur.execute('select name, detail, pic, watched, line from tmpselected where name not in (select name from medialist)')
        newidarr = []
        newlinearr = []
        for row in cur:
            print('loadSelected B:' + row[2])
            newitem = (self.maxnum,row[0],row[1],row[2],row[3])
            newidarr.append(newitem)
            jsonlines = json.loads(row[4])
            for line in jsonlines:
                newline = (self.maxnum,line['apiurl'],line['apitype'],line['vid'])
                newlinearr.append(newline)
            self.maxnum = self.maxnum + 1
        for item in newidarr:
            cur.execute('insert into selected (id,name, detail, pic, watched) VALUES (?,?,?,?,?)', item)
        for line in newlinearr:
            cur.execute('insert into lines (id,url,decodetype,vid) VALUES (?,?,?,?)', line)
        self.dbconn.commit()
        cur.close()
        
    def saveSelected(self):
        outjson = []
        cur = self.dbconn.cursor()
        curline = self.dbconn.cursor()
        cur.execute('select id,name, detail, pic, watched from selected')
        for row in cur:
            item = {}
            item['name'] = row[1]
            item['info'] = row[2]
            item['picture'] = row[3]
            item['actwatched'] = row[4]
            item['linelist'] = []
            sqlstr = 'select url,decodetype,vid from lines where id = ' + str(row[0])
            print(sqlstr)
            curline.execute(sqlstr)
            for linerow in curline:
                newline = {'apiurl':linerow[0],'apitype':linerow[1],'vid':linerow[2]}
                item['linelist'].append(newline)
            outjson.append(item)
        cur.close()
        curline.close()
        with open('userselect.json', 'w',encoding='utf-8') as f:
            json.dump(outjson, f,sort_keys=True, indent=4, separators=(',', ':'), ensure_ascii=False)
        
    def getMediaInfo(self,url,vid,gettype):
        apiurl = url + '?ac=videolist&ids=' + str(vid)
        rescode = 0
        try:
            res = requests.get(apiurl,timeout = 2,verify = False)
            rescode = res.status_code
        except:
            rescode = -100
        if  rescode == 200:
            if gettype == 'json':
                jsondata = None
                try:
                    jsondata = json.loads(res.text, strict = False)
                except:
                    print('读取json数据失败')
                if jsondata:
                    medialist = jsondata['list']
                    if len(medialist) > 0:
                        info = medialist[0]
                        playfrom = info["vod_play_from"]
                        playnote = '$$$'
                        playfromlist = playfrom.split(playnote)
                        playurl = info["vod_play_url"]
                        playurllist = playurl.split(playnote)
                        sourcelen = len(playfromlist)
                        sourcelist = []
                        for i in range(sourcelen):
                            if playfromlist[i].find('m3u8') >= 0:
                                urllist = [] 
                                urlstr = playurllist[i]
                                jjlist = urlstr.split('#')
                                for jj in jjlist:
                                    jjinfo = jj.split('$')
                                    urllist.append({'title':jjinfo[0],'url':jjinfo[1]})
                                sourcelist.append({'flag':playfromlist[i],'medias':urllist}) 
                        return sourcelist
            else:
                bs = bs4.BeautifulSoup(res.content.decode('UTF-8','ignore'),'html.parser')
                selector = bs.select('rss > list > video')
                if len(selector) > 0:
                    info = selector[0]
                    nameinfo = info.select('name')[0]
                    name = nameinfo.text
                    picinfo = info.select('pic')[0]
                    pic = picinfo.text
                    actorinfo = info.select('actor')[0]
                    actor = '演员:' + actorinfo.text.strip()
                    desinfo = info.select('des')[0]
                    des = '简介:' + desinfo.text.strip()
                    dds = info.select('dl > dd')
                    sourcelist = []
                    for dd in dds:
                        ddflag = dd.get('flag')
                        ddinfo = dd.text
                        m3u8list = []
                        if ddflag.find('m3u8') >= 0:
                            urllist = ddinfo.split('#')
                            n = 1
                            for source in urllist:
                                urlinfo = source.split('$')
                                if len(urlinfo) == 1:
                                    m3u8list.append({'title':'第' + str(n) + '集','url':ddinfo})
                                else:
                                    m3u8list.append({'title':urlinfo[0],'url':urlinfo[1]})
                                n = n + 1
                            sourcelist.append({'flag':ddflag,'medias':m3u8list})
                    return sourcelist
        return None
        
    
    
    def show(self):
        controls = self.makeLayout()
        self.doModal('main',800,700,'',controls)        
    
    def makeLayout(self):
        day_layout = [
            {'type':'link','name':'title','@click':'onDayMenuClick'}
        ]

        mediagrid_layout = []
        controls = []
        if self.upvision:
            mediagrid_layout = [
                [
                    {
                        'group': [
                            {'type':'image','name':'picture', '@click':'on_grid_click'},
                            {'type':'link','name':'title','textColor':'#ff7f00','height':20, '@click':'on_grid_click'},
                            {'type':'check','name':'追番','textColor':'#ff0f00','height':20,'@click':'on_grid_select'}
                        ],
                        'dir':'vertical'
                    }
                ]
            ]
            controls = [
                {'type':'space','height':5},
                {'group':
                    [
                        {'type':'space','width':10},
                        {'type':'link','name':'新番列表','@click':'onDayListClick'},
                        {'type':'link','name':'追番列表','@click':'onSelectClick'}
                    ],
                    'height':25
                },
                {'type':'space','height':10},
                {'type':'grid','name':'daygrid','itemlayout':day_layout,'value':self.dayarr,'itemheight':30,'itemwidth':80,'height':25},
                {'type':'space','height':5},
                {'type':'grid','name':'mediagrid','itemlayout':mediagrid_layout,'value':self.actMedias,'separator':True,'itemheight':240,'itemwidth':150},
                {'group':
                    [
                        {'type':'space'},
                        {'group':
                            [
                                {'type':'label','name':'cur_page',':value':'cur_page'},
                                {'type':'link','name':'首页','@click':'onClickFirstPage'},
                                {'type':'link','name':'上一页','@click':'onClickFormerPage'},
                                {'type':'link','name':'下一页','@click':'onClickNextPage'},
                                {'type':'link','name':'末页','@click':'onClickLastPage'},
                                {'type':'label','name':'max_page',':value':'max_page'},
                            ]
                            ,'width':0.7
                        },
                        {'type':'space'}
                    ]
                    ,'height':30
                },
                {'type':'space','height':5}
            ]
        else:
            mediagrid_layout = [
                [
                    {
                        'group': [
                            {'type':'image','name':'picture', '@click':'on_grid_click'},
                            {'type':'link','name':'title','textColor':'#ff7f00','height':20, '@click':'on_grid_click'},
                            #{'type':'check','name':'追番','textColor':'#ff0f00','height':20,'@click':'on_grid_select'}
                        ],
                        'dir':'vertical'
                    }
                ]
            ]
            controls = [
                {'type':'space','height':5},
                {'group':
                    [
                        {'type':'space','width':10},
                        {'type':'link','name':'新番列表','@click':'onDayListClick'},
                        #{'type':'link','name':'追番列表','@click':'onSelectClick'}
                    ],
                    'height':25
                },
                {'type':'space','height':10},
                {'type':'grid','name':'daygrid','itemlayout':day_layout,'value':self.dayarr,'itemheight':30,'itemwidth':80,'height':25},
                {'type':'space','height':5},
                {'type':'grid','name':'mediagrid','itemlayout':mediagrid_layout,'value':self.actMedias,'separator':True,'itemheight':240,'itemwidth':150},
                {'group':
                    [
                        {'type':'space'},
                        {'group':
                            [
                                {'type':'label','name':'cur_page',':value':'cur_page'},
                                {'type':'link','name':'首页','@click':'onClickFirstPage'},
                                {'type':'link','name':'上一页','@click':'onClickFormerPage'},
                                {'type':'link','name':'下一页','@click':'onClickNextPage'},
                                {'type':'link','name':'末页','@click':'onClickLastPage'},
                                {'type':'label','name':'max_page',':value':'max_page'},
                            ]
                            ,'width':0.7
                        },
                        {'type':'space'}
                    ]
                    ,'height':30
                },
                {'type':'space','height':5}
            ]
        return controls
        
    def on_grid_click(self, page, listControl, item, itemControl):
        clickitem = self.actMedias[item]
        self.loading()
        strid = str(self.actMedias[item]['id'])
        sqlstr = 'select url,decodetype,vid from lines where id = ' + strid
        cur = self.dbconn.cursor()
        cur2 = self.dbconn.cursor()
        cur.execute('select watched from selected where id = ' + strid)
        watched = -1
        strwatched = ''
        for row in cur:
            watched = row[0]
        cur.execute(sqlstr)
        allMediaUrls = []
        for row in cur:
            newlines = self.getMediaInfo(row[0],row[2],row[1])
            if newlines:
                for lines in newlines:
                    for medias in lines['medias']:
                        searchsql = 'select count(*) from mediaurls where id = ' + strid + ' and flag = "' + lines['flag'] + '" and url = "' + medias['url'] +'"'
                        cur2.execute(searchsql)
                        if cur2.fetchone()[0] == 0:
                            cur2.execute('insert into mediaurls (id, flag, title, url) VALUES (?,?,?,?)',(self.actMedias[item]['id'],lines['flag'],medias['title'],medias['url']));
                        self.dbconn.commit()
        cur.execute('select DISTINCT flag from mediaurls where id = ' + strid)
        infos = []
        for row in cur:
            flag = row[0]
            cur2.execute('select DISTINCT title,url from mediaurls where id = ' + strid + ' and flag = "' + flag + '"')
            meidalist = []
            for rowtitle in cur2:
                meidalist.append({'title':rowtitle[0],'url':rowtitle[1]})
            if len(meidalist) > watched and watched >= 0:
                strwatched = meidalist[watched]['title']
            infos.append({'flag':flag,'medias':meidalist})
        actmedias = []
        if len(infos) > 0:
            actmedias = infos[0]['medias']
        if strwatched != '':
            strwatched = '上次观看到 ' + strwatched
        mediainfo = {'id':strid,'medianame':self.actMedias[item]['title'],'picture':self.actMedias[item]['picture'],'info':self.actMedias[item]['info'],'source':infos,'watched':strwatched}
        cur.close()
        cur2.close()
        self.loading(True)
        self.createMediaFrame(mediainfo)
    
    def on_grid_select(self, page, listControl, item, itemControl):
        print('on_grid_select')
        newSelected = True;
        if self.actMedias[item]['追番'] == '1':
            self.actMedias[item]['追番'] = '0'
            newSelected = False
        else:
            self.actMedias[item]['追番'] = '1'
        cur = self.dbconn.cursor()
        if newSelected:
            newitem = (self.actMedias[item]['id'],self.actMedias[item]['title'],self.actMedias[item]['info'],self.actMedias[item]['picture'],-1)
            cur.execute('insert or ignore into selected (id,name, detail, pic, watched) VALUES (?,?,?,?,?)', newitem)
            print('insert selected id:' + str(self.actMedias[item]['id']))
        else:
            cur.execute('delete from selected where id = ' + str(self.actMedias[item]['id']))
            print('delete selected id:' + str(self.actMedias[item]['id']))
        self.dbconn.commit()
        cur.close()
        self.saveSelected()
            
    def createMediaFrame(self,mediainfo):  
        if len(mediainfo['source']) == 0:
            self.player.toast('main','该视频没有可播放的视频源')
            return
        actmovies = []
        if len(mediainfo['source']) > 0:
            actmovies = mediainfo['source'][0]['medias']
        medianame = mediainfo['medianame']
        strid = str(mediainfo['id'])
        self.allmovidesdata[strid] = {'name':medianame,'allmovies':mediainfo['source'],'actmovies':actmovies}
        xl_list_layout = {'type':'link','name':'flag','textColor':'#ff0000','width':0.6,'@click':'on_xl_click'}
        movie_list_layout = {'type':'link','name':'title','@click':'on_movieurl_click'}
        controls = [
            {'type':'space','height':5},
            {'group':[
                    {'type':'image','name':'mediapicture', 'value':mediainfo['picture'],'width':150},
                    {'group':[
                            {'type':'label','name':'medianame','textColor':'#ff7f00','fontSize':15,'value':mediainfo['medianame'],'height':40},
                            {'type':'label','name':'info','textColor':'#005555','value':mediainfo['info'],'vAlign':'top'},
                            {'type':'label','name':'userwatched','textColor':'#550055','value':mediainfo['watched'],'vAlign':'top','height':30}
                        ],
                        'dir':'vertical',
                        'width':0.75
                    }
                ],
                'width':1.0,
                'height':250
            },
            {'group':
                [
                    {'type':'space','width':10},
                    {'type':'label','name':'xl','value':'线路','width':60},
                    {'type':'grid','name':'xllist','itemlayout':xl_list_layout,'value':mediainfo['source'],'separator':True,'itemheight':30,'itemwidth':120}
                ],
                'height':40
            },
            {'type':'space','height':5},
            {'group':
                {'type':'grid','name':'movielist','itemlayout':movie_list_layout,'value':actmovies,'separator':True,'itemheight':30,'itemwidth':120},
                'height':200
            }
        ]
        result,control = self.doModal(mediainfo['id'],750,500,'',controls)

    def on_xl_click(self, page, listControl, item, itemControl):
        if len(self.allmovidesdata[page]['allmovies']) > item:
            self.allmovidesdata[page]['actmovies'] = self.allmovidesdata[page]['allmovies'][item]['medias']
        self.player.updateControlValue(page,'movielist',self.allmovidesdata[page]['actmovies'])      
    
    def on_movieurl_click(self, page, listControl, item, itemControl):
        if len(self.allmovidesdata[page]['actmovies']) > item:
            playurl = self.allmovidesdata[page]['actmovies'][item]['url']
            sqlstr = 'select * from selected where id = ' + page
            cur = self.dbconn.cursor()
            c = cur.execute(sqlstr)
            r = len(c.fetchall())
            cur.close()
            if r > 0:
                cur = self.dbconn.cursor()
                strwatched = self.allmovidesdata[page]['actmovies'][item]['title']
                strwatched = '上次观看到 ' +  strwatched
                self.player.updateControlValue(page,'userwatched',strwatched)
                playname = self.allmovidesdata[page]['name'] + ' ' + strwatched
                sqlstr = 'update selected set watched = ' + str(item) + ' where id = ' + page
                print(sqlstr)
                cur.execute(sqlstr)
                self.dbconn.commit()
                self.saveSelected()
                cur.close()
            try:
                self.player.play(playurl, caption=self.allmovidesdata[page]['name'])
            except:
                self.player.play(playurl)          
    
    def onDayMenuClick(self, page, listControl, item, itemControl):
        if self.daylist:
            self.loading()
            self.pageindex = 1
            self.actMedias = self.getSourceOfDay(item)
            self.pagenumbers = self.getPageNumbers()
            self.max_page = '共' + str(self.pagenumbers) + '页'
            self.cur_page = '第' + str(self.pageindex) + '页'
            self.player.updateControlValue('main','mediagrid',self.actMedias)           
            self.loading(True)
        
    def reloadDayList(self):
        sqlstr = ''
        if self.daylist:
            sqlstr = 'select id,name,detail,pic,flag from flagmedialist'
            if self.listday > 0:
                sqlstr = sqlstr + 'where day = ' + str(self.listday)
        else:
            sqlstr = 'select id,name,detail,pic,1 from selected'
        startnum = (self.pageindex  - 1) * self.listnum
        endmum = self.pageindex * self.listnum
        sqlstr = sqlstr + ' limit ' + str(startnum) + ',' + str(endmum)
        print(sqlstr)
        cur = self.dbconn.cursor()
        cur.execute(sqlstr)
        for row in cur:
            newintem = {'id':row[0],'title':row[1],'info':row[2],'picture':row[3],'追番':str(row[4])}
            print(newintem)
            self.actMedias.append(newintem)
        self.pageindex = 1
        maxmedias = len(self.actMedias)
        self.pagenumbers = maxmedias // self.listnum
        if self.pagenumbers * self.listnum < maxmedias:
            self.pagenumbers = self.pagenumbers + 1
        self.max_page = '共' + str(self.pagenumbers) + '页'
        
    def onDayListClick(self, page, Control):
        if self.daylist == False:
            self.daylist = True
        self.player.updateControlValue('main','daygrid',self.dayarr) 
        self.loading()
        self.pageindex = 1
        self.actMedias = self.getSourceOfDay(0)
        self.pagenumbers = self.getPageNumbers()
        self.max_page = '共' + str(self.pagenumbers) + '页'
        self.cur_page = '第' + str(self.pageindex) + '页'
        self.player.updateControlValue('main','mediagrid',self.actMedias)
        self.loading(True)
    
    def onSelectClick(self, page, Control):
        if self.daylist:
            self.daylist = False
        self.player.updateControlValue('main','daygrid',self.zfarr) 
        self.loading()
        self.pageindex = 1
        self.actMedias = self.getSourceOfDay(0)
        self.pagenumbers = self.getPageNumbers()
        self.max_page = '共' + str(self.pagenumbers) + '页'
        self.cur_page = '第' + str(self.pageindex) + '页'
        self.player.updateControlValue('main','mediagrid',self.actMedias)
        self.loading(True)
                
    def reLoadMedias(self):
        self.actMedias = self.getSourceOfDay(self.listday)
        self.player.updateControlValue('main','mediagrid',self.actMedias)
        self.max_page = '共' + str(self.pagenumbers) + '页'
        self.cur_page = '第' + str(self.pageindex) + '页'
        
    def onClickFirstPage(self, *args):
        self.pageindex = 1
        self.loading()
        self.reLoadMedias()
        self.loading(True)
        
    def onClickFormerPage(self, *args):
        if self.pageindex == 1:
            return
        self.pageindex = self.pageindex - 1;
        self.loading()
        self.reLoadMedias()
        self.loading(True)
    
    def onClickNextPage(self, *args):
        if self.pageindex >= self.pagenumbers:
            return
        self.pageindex = self.pageindex + 1
        self.loading()
        self.reLoadMedias()
        self.loading(True)
        
    def onClickLastPage(self, *args):
        self.pageindex = self.pagenumbers
        self.loading()
        self.reLoadMedias()
        self.loading(True)
            
    def playMovieUrl(self,playpageurl):
        return
        
    def loading(self, stopLoading = False):
        if hasattr(self.player,'loadingAnimation'):
            self.player.loadingAnimation('main', stop=stopLoading)
        
def newPlugin(player:StellarPlayer.IStellarPlayer,*arg):
    plugin = yszfplugin(player)
    return plugin

def destroyPlugin(plugin:StellarPlayer.IStellarPlayerPlugin):
    plugin.stop()