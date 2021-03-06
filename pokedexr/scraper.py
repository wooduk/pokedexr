# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01_scraper.ipynb (unless otherwise specified).

__all__ = ['bulba_url_for', 'sanitize_name', 'fetch_page_soup', 'save_card_list', 'load_card_list', 'fetch_card_list',
           'dedupe_image_urls', 'extract_image_urls', 'IMG_EXCEPTIONS', 'isTrainerCard', 'extract_pokemon_card_text',
           'extract_trainer_card_text', 'extract_card_text', 'get_card_numbers', 'update_card_details', 'fetch_image',
           'save_image', 'fetch_images_for_cards', 'PROJ_HOME', 'fetch_card_img_s3']

# Cell
import os
from io import BytesIO
import re
import pickle
import logging
from pathlib import Path

from IPython.core.display import display, HTML
from tqdm import tqdm
import requests
from bs4 import BeautifulSoup
import boto3


# Cell
def bulba_url_for(resource):
    """Returns full url for bulbapedia page given last part or url (resource)"""
    return f"https://bulbapedia.bulbagarden.net/wiki/{resource}"

# Cell
def sanitize_name(name):
    """For extracting images we need a cleaned up version of the card name
    that appears in Deck of set lists
    """
    return re.sub(re.compile('|'.join(['[ &.-:]',"'s"])), '', name)#.replace("'s",'')

# Cell
def fetch_page_soup(resource):
    """Fetches a page and returns a beautiful soup."""
    r = requests.get(bulba_url_for(resource))
    if r.ok:
        soup = BeautifulSoup(r.content, 'html.parser')
    else:
        soup = None
        logging.error(f"Couldn't fetch resource {bulba_url_for(resource)}.")
    return soup

# Cell
def save_card_list(cards, fname='cards.pkl'):
    """Pickles the card list"""
    with open(fname,'wb') as f:
        pickle.dump(cards,f)

# Cell
def load_card_list(cards, fname='cards.pkl'):
    """Load a pickled card list"""
    with open(fname,'rb') as f:
        d = pickle.load(f)
    return d

# Cell
def fetch_card_list(list_name, req_decks=[]):
    """Returns a list of card names, numbers and links to details pages from given list

    list_name -- reference to the page containing the list on bulbapedia
    decks -- decks to be taken from a desk list, ignored for set list
    """
    cards={}
    soup = fetch_page_soup(list_name)

    # is this a Deck List or Set List?
    list_tables = {lt:soup.find(id=lt) for lt in ['Deck_lists', 'Set_list']}

    if list_tables['Deck_lists'] is not None:
        # retrieve the table right after the 'Deck Lists' heading
        deck_lists_tables = soup.find_all('table',{"class": "multicol"})

        # Pull out the required deck lists
        for t in deck_lists_tables:
            for deck in req_decks:
                e=t.find_all('b',text=deck)
                if len(e) > 0:
                    _deck = e[0].parent.parent.parent.parent.parent.parent.parent

                    for row in _deck.find_all('tr')[4:]:
                        try:
                            number, name, _ = row.find_all('td')
                            durl = name.a.attrs.get('href').split('/')[-1]
                            card = {'number':number.text.strip(), 'name': name.a.text, 'details_page_ref': durl}
                            cards[card['name']] = card
                        except:
                            pass
    elif list_tables['Set_list'] is not None:
        set_list_table = list_tables['Set_list'].findNext('table')
        for row in set_list_table.find_all('a',{'class':'mw-redirect'}):
            if row:
                card = {
                    'number':row.parent.parent.find('td').text.strip(),
                    'name': row.text,
                    'details_page_ref': row.attrs.get('href').split('/')[-1]
                }
                cards[card['name']]=card
    else:
        logging.error(f'Could not fetch deck or set list {list_name}')

    # add santized names
    for card_name,card in cards.items():
        card.update({'sname':sanitize_name(card_name)})

    return cards

# Cell
def dedupe_image_urls(urls):
    """Try to de-duplicate a list of image urls given the path structure"""
    deduped_img_urls = {}
    for u in urls:
        k = '/'.join(u.split('/')[:-1])
        deduped_img_urls[k] = u.split('/')[-1]

    return [k+'/'+deduped_img_urls[k] for k in deduped_img_urls]

# Cell
IMG_EXCEPTIONS = {'Devoured_Field_(GX_Starter_Deck_128)':'Decaying_Wasteland_()'}

def extract_image_urls(soup, name):
    """Given the details page soup, extract image urls"""
    card_images = soup.findAll('img',{'alt':re.compile(name)})
    return dedupe_image_urls(list(set([i.get('src') for i in card_images])))

# Cell
def isTrainerCard(soup):
    """Given the soup of card details page, detect if this is a trainer card."""
    s = soup.find(href='/wiki/Trainer_card_(TCG)')
    if s is None:
        return False
    else:
        return True

# Cell
def extract_pokemon_card_text(card_text_table):
    """Given the soup of the details page, return the card text for a trainer card."""
    items=[]
    current_title=None

    japanese_chars = [chr(c) for c in range(0x3040,0x30ff)]
    japanese_chars_re ='['+''.join(japanese_chars)+']'

    for i,table in enumerate(card_text_table.find_all('table')):
        table_text=table.text.strip().replace('\n','')

        if re.search(japanese_chars_re,table_text):

            energy_items = [i.attrs.get('alt') for i in table.find_all('img')]

            # we are looking at a name item because of the japanese characters
            tokens = table_text.split(' ')
            try:
                points=int(tokens[-1])
                name={'jp':tokens[-2], 'en':' '.join(tokens[:-2])}
            except:
                # Some moves have no points associated
                points=None
                name={'jp':tokens[-1], 'en':' '.join(tokens[:-1])}

            current_title = {
                'name': name,
                'points':points
            }
        else:
                desc=table_text if len(table_text) else None
                # a description for current move
                current_item={}
                if current_title:
                    current_item['type']='move'
                    current_item['description']=desc
                    current_item['energy_items']=energy_items
                    current_item.update(current_title)
                elif len(table_text)>0:
                    current_item['type']='info'
                    current_item['description']=desc



                if current_item.get('type',False):
                    items.append(current_item)

                current_title = None

    return items


# Cell
def extract_trainer_card_text(card_text_table):
    """Given the soup of the details page, return the card text for a trainer card."""
    items=[]
    for i,tag in enumerate(card_text_table):
        if not ('display:none' in str(tag)):
            if tag.name == 'tr':
                for td in tag.findChildren('table'):
                    ctd=td.find('td')
                    if not ctd:
                        continue
                    current_item = {'type':'info', 'description':ctd.text.strip()}
                    items.append(current_item)
    return items


# Cell
def extract_card_text(soup):
    """Given the soup for a details page, return any available card text"""
    card_text_title = soup.find(id='Card_text')
    if card_text_title is not None:
        if isTrainerCard(soup):
            card_text = extract_trainer_card_text(card_text_title.findNext())
        else:
            card_text = extract_pokemon_card_text(card_text_title.findNext())
    else:
        card_text=None
    return card_text

# Cell
def get_card_numbers(soup):
    """Given the details page soup, extract any available card numbers"""
    en_nums = soup.find_all(text='English card no.')
    en_nums = list(set([e.find_next().text.strip() for e in en_nums]))
    jp_nums=soup.find_all(text='Japanese card no.')
    jp_nums = list(set([e.find_next().text.strip() for e in jp_nums]))
    return {'alt_card_num': { 'jp': jp_nums, 'en': en_nums }}


# Cell
def update_card_details(cards):
    """Procedure: Given a list of cards (output of fetch_card_lists()) augment the list with the relevant details."""
    for card_name,card in tqdm(cards.items()):

        # fetch details page
        soup=fetch_page_soup(card.get('details_page_ref','notexist'))

        if soup is not None:

            # extract and add the image urls
            card.update({'img_urls': extract_image_urls(soup,card.get('sname'))})

            # extract card text
            card.update({'card_text': extract_card_text(soup)})

            # get alternative card numbers
            card.update({'alt_card_num': get_card_numbers(soup)})

        else:
            logging.warning(f"Couldn't fetch page: {bulba_url_for(card.get('details_page_ref'))}")

    return None


# Cell
def fetch_image(img_url):
    """Given a url produced by extract_image_urls() fetch the image content (bytes) and the filename."""
    r = requests.get(f'https:{img_url}')
    if r.ok:
        data = r.content
        fname = img_url.split('/')[-1]
    else:
        logging.warning(f'Failed to fetch image {img_url}')
        data=None;fname=None
    return (data, fname)



# Cell
def save_image(image_data, fname):
    if 's3' in fname[:2]:
        # push to an s3 bucket
        s3 = boto3.resource('s3')
        bucket=s3.Bucket(fname[3:].split('/')[0])
        key='/'.join(fname[3:].split('/')[1:])
        ret = bucket.put_object(Key=key, Body=BytesIO(image_data))
        if not ret:
            logging.error(f"Failed to upload {fname} to S3.")
        return ret
    else:
        # assume local file
        p=Path(os.path.dirname(fname))
        p.mkdir(parents=True, exist_ok=True)
        with open(fname,'wb') as f:
            f.write(image_data)


# Cell
PROJ_HOME = f"{os.environ['HOME']}/projects/pokemon/"
def fetch_images_for_cards(cards):
    for card_name, card in tqdm(cards.items()):
        for url in card.get('img_urls'):
            image_data, fname = fetch_image(url)
            # folder structure: bucket / card_images / original / <class> / <filename>
            #location = f"s3:{BUCKET_NAME}/card_images/original/{card.get('name')}"
            lfname = f"{PROJ_HOME}/original/{card.get('sname')}/{fname}"
            save_image(image_data, lfname)


# Cell
import PIL
def fetch_card_img_s3(name,bucket=os.environ.get('POKEDEXR_S3')):
    s3 = boto3.resource('s3')
    x=s3.Object(bucket, f'card_images/original/{name}').get()
    src_img = PIL.imread(BytesIO(x['Body'].read()),0)
    return src_img