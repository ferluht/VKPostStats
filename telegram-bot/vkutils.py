import vk
import re
import json
from time import sleep
from datetime import datetime, date, timedelta

def vk_connect(token):
    sess = vk.Session(access_token=token)
    api = vk.API(sess, v='5.92')
    return api

def get_posts_with_audio(api, artist='ϿΔ9M', debug=False):
    end_time = int(datetime.now().timestamp())
    start_time = end_time - 31536000

    links = []

    posts = api.newsfeed.search(q=artist, extended=True, start_time=start_time, end_time=end_time, count=200)

    while 'count' in posts and posts['count'] > 0 and posts['items'][0]['date'] > start_time:

        for post in posts['items']:

            if 'attachments' in post:
                found = False
                for attachment in post['attachments']:
                    if attachment['type'] == 'audio' and artist.lower() in attachment['audio']['artist'].lower():
                        link = 'https://vk.com/wall{}_{}'.format(post['owner_id'], post['id'])
                        found = True
                        links.append(link)
                    if found:
                        break
            if debug:
                print(post)

        if 'next_from' in posts:
            next_from = posts['next_from']
        else:
            break

        posts = api.newsfeed.search(q=artist, extended=True, count=200, start_from=next_from)

    return links[::-1]

def get_reposts(post_urls, group_id=None, debug=False, waittime=0.4):

    if not isinstance(post_urls, (list,)):
        post_urls = [post_urls,]

    def wait():
        sleep(waittime)

    reposts = {
        'group': [],
        'name': [],
        'profile': [],
        'repost text': [],
        'repost likes': [],
        'repost comments': [],
        'repost link': [],
        'group member': []
    }

    for post_url in post_urls:

        owner_id = int(re.search('.*wall(.*)_.*', post_url).group(1))
        item_id = int(re.search('.*_(.*)', post_url).group(1))
        likes_list = api.likes.getList(type='post', owner_id=owner_id, item_id=item_id, count=1000)#, extended=True)

        group_name = api.groups.getById(group_ids=str(abs(owner_id)))[0]['name']

        for user in tqdm(likes_list['items']):
            user_info = api.users.get(user_ids=int(user))
            wait()
            if isinstance(user_info, (list,)):
                    user_info = user_info[0]
            try:
                wall = api.wall.get(owner_id=user)
                wait()
                for post in wall['items']:
                    if 'copy_history' not in post:
                        continue
                    pts = json.dumps(post)
                    for ch in post['copy_history']:
                        if ch['owner_id'] == owner_id and ch['id'] == item_id:
                            reposts['group'].append(group_name)
                            reposts['name'].append(user_info['first_name'] + ' ' + user_info['last_name'])
                            reposts['profile'].append('https://vk.com/id' + str(user_info['id']))
                            reposts['repost text'].append(post['text'])
                            reposts['repost likes'].append(post['likes']['count'])
                            reposts['repost comments'].append(post['comments']['count'])
                            reposts['repost link'].append('{}?w=wall{}_{}'.format(reposts['profile'][-1], post['owner_id'], post['id']))
                            reposts['group member'].append('N/A')
                            if group_id is not None:
                                try:
                                    ismember = api.groups.isMember(group_id=group_id, user_id=user_info['id'])
                                    reposts['group member'][-1] = bool(ismember)
                                except:
                                    pass
                                wait()

                            if debug:
                                print(post)

            except Exception as error:
                if debug:
                    print(user_info['first_name'] + ' ' + user_info['last_name'] + ' ' + str(error))

    return reposts
