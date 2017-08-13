
# coding: utf-8

# In[1]:

import xml.etree.cElementTree as ET
import csv
from collections import defaultdict
import cerberus
import schema
import codecs
import pprint 

## k value for sample file 
k = 50 

## Function for iterating through the main tags 
def extract_context(osm_file, tags=('node', 'way', 'relation')):
    ## Get elements from start to end
    context_1 = iter(ET.iterparse(osm_file, events=('start','end')))
    _, root = next(context_1)
    for event,elem in context_1:
        if event == 'end' and elem.tag in tags:
            yield elem  
            root.clear()

## Create the new sample file 
with open('Melbourne_Map_Sample.xml', 'wb') as output:
    output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    output.write('<osm>\n  ')
    
    for i,element in enumerate(extract_context('Melbourne_Map')):
        if i % k == 0:
            output.write(ET.tostring(element, encoding='utf-8'))
    
    output.write('</osm>')





# In[2]:

## Get an idea of all the different tags in the dataset 
def count_tags(filename):
        tags = {}
        parser = ET.iterparse(filename) 
        for __, elem in parser:
            ## Add 1 to each unique tag found
            if elem.tag in tags:
                tags[elem.tag] += 1
            else:
                tags[elem.tag] = 1
                
            elem.clear()
        del parser
        return tags 

count_tags("Melbourne_Map_Sample.xml") 


# In[3]:

## Get all unique k values 
def extract_k_values(filename):
    osm_file = open(filename,"r")
    name_types = set()
    for __, elem in ET.iterparse(filename, events=("start",)):
        
        if elem.tag == "node" or elem.tag == "way" or elem.tag == "relation":
            for tag in elem.iter('tag'):
                try:
                    name_types.add(tag.attrib['k'])
                except KeyError:
                    continue 
                        
    print name_types

extract_k_values('Melbourne_Map_Sample.xml') 



# In[4]:

import re

## Search for the last word for the value of the given k

street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)
street_types = defaultdict(int)

def audit_street_type(street_types, street_name): 
    m = street_type_re.search(street_name)
    if m:
        street_type = m.group()
        street_types[street_type] += 1

## print function for printing k values
def print_sorted_dict(d):
    keys = d.keys()
    keys = sorted(keys, key=lambda s:s.lower())
    for k in keys:
        v = d[k]
        print "%s: %d" % (k,v)

## Checks whether or not k exists 
def is_name(elem, name_type):
    return (elem.attrib['k'] == name_type)


def audit_tags(name_type):
    osm_file = open("Melbourne_Map_Sample.xml") 
    print name_type, "\n"
    for event, elem in ET.iterparse(osm_file, events=("start",)):
        if elem.tag == "way" or elem.tag == "node" or elem.tag == "relation":
            for tag in elem.iter("tag"):
                if is_name(tag, name_type):
                    audit_street_type(street_types, tag.attrib['v'])
    
    osm_file.close() 
    print_sorted_dict(street_types)
    street_types.clear()

## Searching through k-values randomly or ones that are common in having errors 

## audit_tags('addr:country')
## audit_tags('postal_code')
## audit_tags('exit_to')
## audit_tags('addr:city')
## audit_tags('addr:postcode')
## audit_tags('amenity')
audit_tags('addr:state')


# In[5]:


## Set name for csv files to which XML data will be exported
NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

## Search for colon (:) and problemchars 
LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

## Set which keys/values will be extracted from tag
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']

## Clean up any inconsistency found through querying or earlier through trial and error checking
## Returns new{}, a dictionary with the new cleaned data 
def clean_tag(element,secondary,default_tag_type):
    new = {}
    new['id'] = element.attrib['id']
    if ":" not in secondary.attrib['k']:
        new['key'] = secondary.attrib['k']
        new['type'] = default_tag_type 
    
    else:
        post_colon = secondary.attrib['k'].index(":") + 1
        new['key'] = secondary.attrib['k'][post_colon:]
        new['type'] = secondary.attrib['k'][:post_colon-1]
    
    ## Clean inconsistency in addr:state 
    if new['key'] == 'state':
        original_value = secondary.attrib['v']
        if original_value == 'VIC':
            original_value = "Victoria"
        
        new['value'] = original_value 
    
    ## Clean up inconsistency in sources (Inconsistent in lower and upper case)
    elif new['key'] == 'source':
        original_value = secondary.attrib['v']
        if original_value == 'survey;yahoo':
            original_value = 'survey;Yahoo'
        if original_value == 'yahoo':
            original_value = 'Yahoo'
        if original_value == 'bing':
            original_value = 'Bing'
            
        new['value'] = original_value
    
    else:
        new['value'] = secondary.attrib['v']
    
    return new 

class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

## Iterates through the parent tag e.g. node and gets all wanted attributes 
def shape_element(element,node_attr_fields=NODE_FIELDS,way_attr_fields=WAY_FIELDS,problem_chars=PROBLEMCHARS,
                 default_tag_type='regular'):
    
    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []
    
    ## Getting attributes in node tags
    if element.tag == "node":
        for attrib,value in element.attrib.iteritems():
            if attrib in node_attr_fields:
                node_attribs[attrib] = value
        
        for secondary in element.iter():
            if secondary.tag == 'tag':
                if problem_chars.match(secondary.attrib['k']) is not None:
                    continue
                else:
                    ## Using clean_tag to make sure data is cleaned up
                    new = clean_tag(element, secondary, default_tag_type)
                    if new is not None:
                        tags.append(new)
    
        return {'node':node_attribs, 'node_tags':tags}
    
    ## Getting attributes in way tags
    if element.tag=="way":
        for attrib,value in element.attrib.iteritems():
            if attrib in way_attr_fields:
                way_attribs[attrib] = value
        
        counter = 0
        for secondary in element.iter():
            if secondary.tag == "tag":
                if problem_chars.match(secondary.attrib['k']) is not None:
                    continue
                else:
                    new = clean_tag(element, secondary, default_tag_type)
                    if new is not None:
                        tags.append(new)
            
            if secondary.tag == 'nd':
                newnd = {}
                newnd['id'] = element.attrib['id']
                newnd['node_id'] = secondary.attrib['ref']
                newnd['position'] = counter
                counter += 1
                way_nodes.append(newnd)
        
        return {'way':way_attribs, 'way_nodes':way_nodes, 'way_tags':tags} 
    
## Export data to csv files
def process_map(file_in, validate):
    
    with codecs.open(NODES_PATH, "w") as nodes_file,codecs.open(NODE_TAGS_PATH, "w") as nodes_tags_file,codecs.open(WAYS_PATH, "w") as ways_file, codecs.open(WAY_NODES_PATH, "w") as way_nodes_file,codecs.open(WAY_TAGS_PATH, "w") as way_tags_file:
            
        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        
        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()
        
        validator = cerberus.Validator()
        
        for element in extract_context(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                
                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag=='way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])


process_map("Melbourne_Map_Sample.xml", validate=True)


# In[6]:

import sqlite3

sqlite_file = "mydv.db"
conn = sqlite3.connect(sqlite_file)
cur = conn.cursor() 

## Load nodes.csv into database
cur.execute('DROP TABLE IF EXISTS nodes')
conn.commit()
cur.execute(''' CREATE TABLE nodes(id INTEGER, lat FLOAT, lon FLOAT, user TEXT, uid INTEGER, version INTEGER,
            changeset INTEGER, timestamp TEXT)''')
conn.commit()
with open("nodes.csv", "rb") as fin:
    dr = csv.DictReader(fin)
    to_db = [(i['id'].decode("utf-8"), i['lat'].decode("utf-8"), i['lon'].decode("utf-8"), 
              i['user'].decode("utf-8"), i['uid'].decode("utf-8"),i['version'].decode("utf-8"),
              i['changeset'].decode("utf-8"),i['timestamp']) for i in dr]
cur.executemany("INSERT INTO nodes(id,lat,lon,user,uid,version,changeset,timestamp) VALUES(?,?,?,?,?,?,?,?);", to_db)
conn.commit() 

## Load ways_nodes.csv into database
cur.execute('DROP TABLE IF EXISTS ways_nodes')
conn.commit()
cur.execute(''' CREATE TABLE ways_nodes(id INTEGER, node_id INTEGER, position INTEGER)''')
conn.commit()
with open("ways_nodes.csv", "rb") as fin:
    dr = csv.DictReader(fin)
    to_db = [(i['id'].decode("utf-8"), i['node_id'].decode("utf-8"), i['position'].decode("utf-8")) for i in dr]
cur.executemany("INSERT INTO ways_nodes(id,node_id,position) VALUES(?,?,?);", to_db)
conn.commit() 

## Load ways_tags.csv into database
cur.execute('DROP TABLE IF EXISTS ways_tags')
conn.commit()
cur.execute('''CREATE TABLE ways_tags(id INTEGER,key TEXT,value TEXT,type TEXT)''')
conn.commit()
with open("ways_tags.csv", "rb") as fin:
    dr = csv.DictReader(fin)
    to_db = [(i['id'].decode("utf-8"), i['key'].decode("utf-8"),i['value'].decode("utf-8"),i['type'].decode("utf-8")) for i in dr]
cur.executemany("INSERT INTO ways_tags(id,key,value,type) VALUES(?,?,?,?);", to_db)
conn.commit() 

## Load ways.csv into database
cur.execute('DROP TABLE IF EXISTS ways')
conn.commit()
cur.execute(''' CREATE TABLE ways(id INTEGER, user TEXT, uid INTEGER, version INTEGER, changeset INTEGER, timestamp TEXT)''')
conn.commit()
with open("ways.csv", "rb") as fin:
    dr = csv.DictReader(fin)
    to_db = [(i['id'].decode("utf-8"),i['uid'].decode("utf-8"), i['user'].decode("utf-8"),i['version'].decode("utf-8"), i['changeset'].decode("utf-8"), i['timestamp'].decode("utf-8")) for i in dr]
cur.executemany("INSERT INTO ways(id, uid, user, version, changeset, timestamp) VALUES(?,?,?,?,?,?);", to_db)
conn.commit()

## Load nodes_tags.csv into database 
cur.execute('DROP TABLE IF EXISTS nodes_tags')
conn.commit()
cur.execute('''CREATE TABLE nodes_tags(id INTEGER,key TEXT,value TEXT,type TEXT, FOREIGN KEY (id) REFERENCES nodes(id)) ''')
conn.commit() 
with open("nodes_tags.csv",'rb') as fin:
    dr = csv.DictReader(fin)
    to_db = [(i['id'].decode("utf-8"), i['key'].decode("utf-8"), i['value'].decode("utf-8"), i['type'].decode("utf-8")) for i in dr]
cur.executemany("INSERT INTO nodes_tags(id,key,value,type) VALUES(?,?,?,?);",to_db)
conn.commit() 


# In[7]:

## Number of unique users
cur.execute("SELECT COUNT(DISTINCT(uid)) FROM (SELECT uid FROM nodes UNION ALL SELECT uid FROM ways);")
all_uid = cur.fetchall()
print "Number of unique users"
print all_uid[0][0], "\n" 

cur.execute("SELECT uid, COUNT(uid) FROM (SELECT uid FROM nodes UNION ALL SELECT uid FROM ways)")

## Number of nodes
cur.execute("SELECT COUNT(*) FROM nodes;")
all_nodes = cur.fetchall()
print "Number of nodes"
print all_nodes[0][0], "\n"

## Number of ways 
cur.execute("SELECT COUNT(*) FROM ways;")
all_ways = cur.fetchall()
print "Number of ways"
print all_ways[0][0], "\n" 

## Top ten contributing users
cur.execute("SELECT e.user, COUNT(*) as num FROM (SELECT user FROM nodes UNION ALL SELECT user FROM ways) e GROUP BY e.user ORDER BY num DESC LIMIT 10;")
all_vals = cur.fetchall()
print "Different users"
print all_vals, "\n"

## Different amenities in nodes_tags
cur.execute("SELECT key,value, COUNT(value) FROM nodes_tags WHERE key ='amenity' GROUP BY value LIMIT 10")
all_rows = cur.fetchall()
print "Amenities in Melbourne from nodes_tags"
print all_rows, "\n" 

cur.execute("SELECT COUNT(*) FROM nodes_tags WHERE key='amenity' ") 
all_tours = cur.fetchall()
print "Number of different amenities from nodes_tags"
print all_tours[0][0], "\n"

## Different amenities in ways_tags
cur.execute("SELECT key,value, COUNT(value) FROM ways_tags WHERE key ='amenity' GROUP BY value")
all_rows = cur.fetchall()
print "Amenities in Melbourne from ways_tags"
print all_rows, "\n" 

cur.execute("SELECT COUNT(*) FROM ways_tags WHERE key='amenity' ") 
all_tours = cur.fetchall()
print "Number of different amenities from ways_tags"
print all_tours[0][0], "\n"

## Different sources in nodes_tags
cur.execute("SELECT key,value, COUNT(value) FROM nodes_tags WHERE key ='source' GROUP BY value")
all_rows = cur.fetchall()
print "Sources in Melbourne from nodes_tags"
print all_rows, "\n" 

cur.execute("SELECT COUNT(*) FROM nodes_tags WHERE key='source' ") 
all_rows = cur.fetchall()
print "Number of different sources from nodes_tags"
print all_rows[0][0], "\n"

## Different sources in ways_tags
cur.execute("SELECT key,value, COUNT(value) FROM ways_tags WHERE key ='source' GROUP BY value")
all_rows = cur.fetchall()
print "Sources in Melbourne from ways_tags"
print all_rows, "\n" 

cur.execute("SELECT COUNT(*) FROM ways_tags WHERE key='source' ") 
all_tours = cur.fetchall()
print "Number of different sources from ways_tags"
print all_tours[0][0], "\n"

## Different networks in nodes_tags
cur.execute("SELECT key,value, COUNT(value) FROM nodes_tags WHERE key ='network' GROUP BY value")
all_rows = cur.fetchall()
print "Networks in Melbourne from nodes_tags"
print all_rows, "\n" 

cur.execute("SELECT COUNT(*) FROM nodes_tags WHERE key='network' ") 
all_rows = cur.fetchall()
print "Number of different networks from nodes_tags"
print all_rows[0][0], "\n"

## Different sources in ways_tags
cur.execute("SELECT key,value, COUNT(value) FROM ways_tags WHERE key ='network' GROUP BY value")
all_rows = cur.fetchall()
print "Networks in Melbourne from ways_tags"
print all_rows, "\n" 

cur.execute("SELECT COUNT(*) FROM ways_tags WHERE key='network' ") 
all_rows = cur.fetchall()
print "Number of different network from ways_tags"
print all_rows[0][0], "\n"


# In[ ]:



