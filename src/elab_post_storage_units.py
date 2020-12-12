
import json
import argparse
import csv
import requests


FILENAME = "../testdata/storagelist.txt"
base_endpoint = 'https://us.elabjournal.com/api/v1'
base_endpoint = 'https://elab.calicolabs.com/api/v1'
default_user = 'cricket@calicolabs.com'


def getArgs():
    
    EPILOG = '''
    Create storage units with sublayers in eLab from a csv
    name,building,floor,room,tetrascience-magnet,manager,department,number-of-shelves,list-of-subunits,notes,storage-type
    '''

    parser = argparse.ArgumentParser(
        description=__doc__, epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--pwd',
                        help="The elab password"
                        )
    parser.add_argument('--usr',
                        default=default_user,
                        help="The elab user"
                        )  
    parser.add_argument('--source',
                        default='Genomics',
                        help="Genomics or Operations or Vivarium style sheet"
                        )                                       
    parser.add_argument('--infile',
                        default=FILENAME,
                        help="A operations style storage unit sheet"
                        )
    parser.add_argument('--debug',
                        default=False,
                        action='store_true',
                        help="Print debug messages.  Default is False.")

    args = parser.parse_args()
    return args


def getAuth (usr,pwd):

    auth_data = {
        'un': usr,
        'pw': pwd
    }

    jar = requests.cookies.RequestsCookieJar()

    r = requests.post(
        'https://elab.calicolabs.com/login/login.ashx',
        data=auth_data,
        cookies=jar
    )
    jar.update(r.cookies)
    print('Authentication status: ',r.status_code)

    auth_response = r.json()
    print(auth_response, jar)

    return jar


def get_storage(row, source):
   
    storageTypes = {
        'RT' : 6, # Shelf
        'Cabinet' : 5, # Cupboard
        'Storage Room': 11, # Storage Room
        '-80C': 1, # -80 Freezer
        'Freezer: -80C': 1, # -80 Freezer
        '-20C': 2, # -20 Freezer
        'Freezer: -20C': 2, # -20 Freezer
        'Freezer: -20C Undercounter': 2, # -20 Freezer
        '-180C': 9, # -180 Freezer
        '4C': 3, # Refrigerator
        'Refrigerator: 4C': 3, # Refrigerator
        'Refrigerator: 4C, Deli': 3, # Refrigerator
        'Refrigerator: 4C, Undercounter': 3, # Refrigerator
    }
    
    storage = {}

    if source in ['Genomics', 'Vivarium']:
        #name,building,floor,room,tetrascience-magnet,manager,department,number-of-shelves,list-of-subunits,notes,storage-type    
        for item in ['name', 'building', 'floor', 'room', 'department']:
            storage[item] = row[item]
        storage['room'] = 'F' + storage['room']
        storage['name'] = storage['department'] + '-' + storage['room'] + ' - ' + storage['name']   
        storage['department'] = source
        storage['storageTypeID'] = storageTypes[row['storage-type']]
        storage['notes'] = row['tetrascience-magnet']
        print ('New Storage:', storage)
    elif source == 'Operations':
        #Manufacturer	Make and Model Number	Serial Number		Type of Equipment  Capital Asset Tag (Green)   Non-Capital Asset Tag (C-#) (Blue)	Other ID or Nickname   Building	Location - Labs/Core/Suites	Primary Calico Users  Status	Tetrascience Monitoring?
        storage['building'] = row['Building']
        roomInfo = row['Location - Labs/Core/Suites'].split('-')
        storage['room'] = roomInfo[0].strip()
        storage['floor'] = ''
        if len(storage['room']) > 1:
            storage['floor'] = storage['room'][1]
        storage['department'] = 'unknown'
        if len(roomInfo) > 1:
            storage['department'] = roomInfo[1].strip()
        storage['storageTypeID'] = 0 # We are missing -40 and combination
        if row['Type of Equipment'] in storageTypes:
            storage['storageTypeID'] = storageTypes[row['Type of Equipment']] 
        storage['notes'] = 'Manufacturer: ' + row['Manufacturer']
        for item in ['Make and Model Number', 'Serial Number', 'Tetrascience Monitoring?']:
           storage['notes'] = storage['notes'] + '\n' + item + ': ' + row[item]
        
        print ('New Storage:', storage)
    return storage


def post_storage(unit, jar):

    r = requests.post(
        base_endpoint + '/storage/',
        cookies=jar,
        json=unit 
    )
    print(r.status_code)
    print(r.json()) 

    #Fix from Erwin
    dimension = {'dimension': {
        'rows':{
            'numbering':'NUMERIC',
            'count':1
            },
        'columns':{
            'numbering':'NUMERIC',
            'count':1}
            }
        } 
    ID = str(r.json()['storageLayerID'])
    r2 = requests.patch(
        base_endpoint + '/storageLayers/' + ID,
        cookies=jar,
        json=dimension 
    )
    print(r2.status_code)
    
    return r.json()


def add_definition(ID, name, jar):

    definition = {
       'icon': 'shelf', 
       'isGrid': False, 
       'name': name, 
       'level': 2, 
       'transposed': False, 
       'dimension': {
           'rows': {
               'numbering': 'NUMERIC', 
               'count': 1
            }, 
            'columns': {
                'numbering': 'NUMERIC', 
                'count': 1
            }
        }
    }    

    r = requests.post(
        base_endpoint + '/storage/' + str(ID) + '/storageLayerDefinitions/',
        cookies=jar,
        json=definition 
    )
    print(r.status_code)
    print('storageLayerDefinitionID',r.json())

    return r.json()


def add_layer(ID, newdef, count, name, jar):

    if name != 'Door':
        name = name + ' ' + str(count + 1)
    
    layer = {
       'storageLayerDefinitionID': newdef,
       'name': name,  
       'transposed': False, 
    }    

    r = requests.get(
        base_endpoint + '/storageLayers/' + str(ID) + '/childLayers/',
        cookies=jar
    )
    print(r.status_code)
    print ('Existing Layers')
    print(r.json()) 


    r = requests.post(
        base_endpoint + '/storageLayers/' + str(ID) + '/childLayers/',
        cookies=jar,
        json=layer 
    )
    print(r.status_code)
    print(r.json()) 

    return r.json()


def main():

    print('')
    print('')

    # Get the command line arguments 
    args = getArgs()

    # Authenticate with eLab
    jar = getAuth(args.usr, args.pwd)

    # Read in the csv file as json
    stream = open(args.infile, newline = '')
    reader = csv.DictReader(stream)

    # For each row in the csv that is not empty:
    for row in reader: 
        if 'name' in row or 'Manufacturer' in row:
            # Convert row into eLab storage object
            storage = get_storage(row, args.source)
            if args.source == 'Genomics': #Limit to only this one for testing 
                storage = post_storage(storage, jar)
                # Create Shelves
                num = int(row['number-of-shelves'])
                if num and num > 0:
                    # Create a storageLayerDefinition for "shelf"
                    print('Adding Shelf defintion')
                    newdef = add_definition(storage['storageID'], 'Shelf', jar)
                    # Create num shelves
                    print('Adding shelves')
                    for x in range(num):
                        newUnit = add_layer(storage['storageLayerID'], newdef, x, 'Shelf', jar)
                # Create Door Shelves
                num = int(row['number-of-doors'])
                if num and num > 0:
                    # Create a storageLayerDefinition for "Door"
                    print('Adding Door defintion')
                    newdef = add_definition(storage['storageID'], 'Door', jar) 
                    #Do I need a new def???
                    door = add_layer(storage['storageLayerID'], newdef, 0, 'Door', jar)
                    # Create num shelves
                    print('Adding shelves')
                    for x in range(num):
                        newUnit = add_layer(door, newdef, x, 'Shelf', jar)
            if args.source == 'Vivarium' and row['name'] != 'Viam Rack 84': #Limit to only this one for testing        
                storage = post_storage(storage, jar)
                # Create Cells
                num = int(row['number-of-shelves'])
                if num and num > 0:
                    # Create a storageLayerDefinition for "shelf"
                    print('Adding Cell defintion')
                    newdef = add_definition(storage['storageID'], 'Cell', jar)
                    # Create num Cell
                    print('Adding Cells')
                    for x in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
                        for y in ['1', '2', '3', '4', '5', '6', '7']:   
                           newPos = add_layer(storage['storageLayerID'], newdef, x+y, 'Cell', jar) 
                           newCage = add_layer(newPos, newdef, '2435', 'Cage', jar)


if __name__ == '__main__':

    main()
