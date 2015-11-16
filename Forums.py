import http.cookiejar
from urllib import request, parse
from bs4 import BeautifulSoup
import re

#Forum object, created for mybb forum software.
class forum(object):
    def __init__(self, ip, ssl = False, port = None):
        self._ip = ip
        if ssl:
            self._protocal = "https"
        else:
            self._protocal = "http"
        self._port = port
        cj = http.cookiejar.CookieJar()
        self._cproc = request.HTTPCookieProcessor(cj)
        self._opener = request.build_opener(self._cproc)
        self._login = False

    @property
    def ip(self):
        return self._ip

    #executes an http POST; returns http response
    def _open(self, url, data = {}):
        self.lastRequest = url
        if data == {}:
            p_data = None
        else:
            p_data = parse.urlencode(data).encode()
        return self._opener.open("{}://{}{}".format(self._protocal, self._ip, url), data = p_data)

    def openPage(self, url):
        resp = self._open(url).read()
        if url.startswith("/forumdisplay.php"):
            return Parser.parseThreadList(resp)
        elif url.startswith("/showthread.php"):
            print("parsing thread")
            return Parser.parseThreadPage(resp)
        else:
            return resp
    
    def respond(self, text, url = None):
        if url is None: url = self.lastRequest
        reg = re.match("/showthread.php\?tid=(\d+)", url)
        if not reg: return 0
        html = self._open(url)
        soup = BeautifulSoup(html, 'html.parser')
        inputs = soup.find("form", method="post", id="quick_reply_form").findAll("input", type="hidden")
        data = {}
        for input in inputs:
            data[input.get("name")] = input.get("value")
        data['message'] = text
        self._open('/newreply.php', data = data)
        return 1

    #logs into the forums
    def login(self, username, password, url = '/index.php'):
        self._login = True
        self.username = username

        DATA = {
            "url": "{}://{}{}".format(self._protocal, self._ip, url),
            "action": "do_login",
            "submit": "Login",
            "quick_login": "1",
            "quick_username": username,
            "quick_password": password
            }

        resp = self._open('/member.php?action=login', DATA)
        if "member_login" in resp.read().decode()[-16]:
            return False
        else:
            self._login = True
            return True
        return


    #searches the given string on the forums. Requeres body & header, resturn a named tuple of the results
    def search(self, searchUrl, params, header = None):
        #Search from search page
        header = header or self._defaultHeader
        try:
            self.resp = self._open(searchUrl, params)
        except request.HTTPError:
            raise self.NoPageFound('Bad response status')
        #get URL from redirect
        soup = BeautifulSoup(self.resp.read(), 'html.parser')
        url = soup.find('a').get('href')
        if url is None:
            raise self.NoRedirect('Redirect link not found.')
        #load search results
        try:
            self.resp = self._open('/{}'.format(url))
        except request.HTTPError:
            raise self.NoPageFound('Bad responsen status')
        self.searchResults = Parser.parseSearchResults(self.resp.read())


    #Generates the default search parameters.
    def genSearchParams(self, keywords):
        params = self._defaultParams
        params['keywords'] = keywords
        return params



    #Default search paramters, without the searchterm
    _defaultParams = {'submit':      'Search',
                     'sortordr':    'desc',
                     'sortby':      'lastpost',
                     'showresults': 'threads',
                     'postthread':  '1',
                     'postdate':    '0',
                     'pddir':       '1',
                     'keywords': None,
                     'forum[]': '1',
                     'findthreadst': '1',
                     'action': 'do_search' }

    #Default header
    _defaultHeader = {"Content-type": "application/x-www-form-urlencoded", 
                                 "submit": "text/plain"}

    #Exception raised when http response does not have status 200
    class NoPageFound(Exception):
        def __init__(self, value):
            self.value = value
        def __str__(self):
            return repr(self.value)
    

    #Exception raised when there is no URL found on the redirect page.
    #This occurs when searching 
    class NoRedirect(Exception):
        def __init__(self, value):
            self.value = value
        def __str__(self):
            return repr(self.value)

class Post(object):
    def __init__(self, poster, time, text, signature):
        self._poster = poster
        self._time = time
        self._text = text
        self._signature = signature
    @property
    def poster(self):
        return self._poster
    @property
    def signature(self):
        return self._signature
    @property
    def text(self):
        return self._text
    @property
    def time(self):
        return self._time 

class ThreadList(object):
    def __init__(self, forum, title, author, reply_count, view_count, last_poster, last_post_time):
        self._title = title
        self._author = author
        self._forum = forum
        self._replc = reply_count
        self._viewc = reply_count
        self._lastpr = last_poster
        self._lastpt = last_post_time
    @property
    def forum(self):
        return self._forum
    @property
    def title(self):
        return self._title
    @property
    def author(self):
        return self._author
    @property
    def reply_count(self):
        return self._replc
    @property
    def view_count(self):
        return self._viewc
    @property
    def last_replier(self):
        return self._lastpr
    @property
    def last_reply_time(self):
        return self._lastpt

class Parser():
        #Parses the html from the result page; returns named tuple of the results
    def parseSearchResults(html):
        results = []
        #tuple = namedtuple('searchResults', ['thread', 'forum', 'author', 'lastreplier', 'lastreplytime'])
        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.findAll('tr', class_ = 'inline_row')
        for row in rows:
            lines = row.findAll('td')

            line = lines[2].find(class_ = ' subject_old')
            if line is None: line = lines[2].find('span', class_ = " subject_editable subject_old")
            title = _parseHref(line)

            line = lines[2].find(class_ = 'author smalltext').find('a')
            author = _parseHref(line)

            line = lines[3].find('a')
            forum_ = _parseHref(line)

            line = lines[6].findAll('a')[-1]
            lastreplier = _parseHref(line)

            lastreplytime = lines[6].find('span').getText().split()[:2]

            view_count = lines[5].getText()

            reply_count = lines[4].getText()

            results.append(ThreadList(forum_, title, author, reply_count, view_count, lastreplier, lastreplytime))
        return results

    def parseThreadList(html):
        results = []
        #tuple = namedtuple('searchResults', ['thread', 'forum', 'author', 'lastreplier', 'lastreplytime'])
        soup = BeautifulSoup(html, 'html.parser')
        forum_ = soup.find('div', class_ = 'navigation').find('span').getText()
        rows = soup.findAll('tr', class_ = 'inline_row')
        for row in rows:
            lines = row.findAll('td')
            
            line = lines[2].find('span', class_ = " subject_new")
            if line is None: line = lines[2].find('span', class_ = " subject_old")
            if line is None: line = lines[2].find('span', class_ = "subject_editable subject_new")
            if line is None: line = lines[2].find('span', class_ = "subject_editable subject_old")
            
            line = line.find('a')
            title = Parser._parseHref(line)

            line = lines[2].find(class_ = 'author smalltext').find('a')
            author = Parser._parseHref(line)

            line = lines[5].findAll('a')[-1]
            lastreplier = Parser._parseHref(line)

            lastreplytime = lines[5].find('span').getText().split()[:2]

            view_count = lines[4].getText()

            reply_count = lines[3].getText()

            results.append(ThreadList((forum_), title, author, reply_count, view_count, lastreplier, lastreplytime))
        return results

    def parseThreadPage(html):
        results = []
        soup = BeautifulSoup(html, 'html.parser')
        posts = soup.findAll('div', class_ = 'post ')
        for post in posts:

            line = post.find('div', class_ = 'author_information')
            poster = [line.findChild().getText()]
            poster.append(line.find('a').get('href'))

            time = post.find('span', class_ = 'post_date').getText().split('(')[0].strip()

            text = post.find('div', class_ = 'post_body scaleimages').getText().strip()

            signature = post.find('div', class_ = 'signature scaleimages').getText().strip()
            results.append(Post(poster, time, text, signature))
        return results
        

    #Parse html, returns tuple containing readable text and the URL
    def _parseHref(line):
        return (line.getText(), line.get('href'))