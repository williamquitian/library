import pandas as pd
from datetime import date, datetime, time
from clients.models import Client, Country, SendMoney, FidelityCard, Broker
from django.contrib.auth import get_user_model
import numpy as np
import re
from dateutil import parser

envios = [["H","I"],["J","K"],["L","M"],["N","O"],["P","Q"],["R","S"],["T","U"],["V","W"],
          ["X","Y"],["Z","AA"],["AB","AC"],["AD","AE"],["AF","AG"],["AH","AI"],["AJ","AK"],
          ["AL","AM"],["AN","AO"],["AP","AQ"],["AR","AS"],["AT","AU"],["AV","AW"],["AX","AY"],
          ["AZ","BA"],["BB","BC"],["BD","BE"],["BF","BG"],["BH","BI"],["BJ","BK"],["BL","BM"],
          ["BN","BO"],["BP","BQ"],["BR","BS"],["BT","BU"]]

User = get_user_model()

def run():
    csv_file_path = '/home/william/Downloads/Sheet1.csv'
    df = pd.read_csv(
            csv_file_path,
            converters={
                'first_name': lambda x: str(x).strip() if pd.notnull(x) else '',
                'last_name': lambda x: str(x).strip() if pd.notnull(x) else '',
                #'date_of_birth': safe_parse_date,
                #'creation_date' : safe_parse_date,
                'phone': clean_phone,
            }
        )
    df = df.replace({np.nan: ''})

    error_messages = []
    
    i = 0
    for index, row in df.iterrows():
        '''
        #print(row['first_name'])
        for env in envios:
            if(row[env[0]] or row[env[1]]):
                try:
                    row[env[0]] = parser.parse(row[env[0]]).date()
                except Exception:
                    i+=1
                    print(f"{i} Error en envío fila:{index+2} columna:{env[0]}")

                try:
                    row[env[1]] = float(row[env[1]].replace("$","").replace(",",""))
                except Exception:
                    i+=1
                    print(f"{i} Error en envío fila:{index+2} columna:{env[1]}")
                #print(f"{env[0]} --> {row[env[0]]}")
                #print(f"{env[1]} --> {row[env[1]].replace("$","").replace(",","")} --> {row[env[1]]}")
        
'''
        if row['first_name'] and (row['phone'] or row['date_of_birth']):
            try:
                match row['country']:
                    case 'COL':
                        row['country'] = 'CO'
                    case 'ELS':
                        row['country'] = 'SV'
                    case 'HD':
                        row['country'] = 'HN'
                    case 'VZ':
                        row['country'] = 'VE'
                    case 'NIC':
                        row['country'] = 'NI'
                    case 'gt':
                        row['country'] = 'GT'
              
                country = Country.objects.get(iso=row['country'].strip())
            except country.DoesNotExist:
                error_messages.append(f"País invalido: fila {index} {row['first_name']} --> {row['country']}")
                continue
            except AttributeError:
                error_messages.append(f"País invalido: fila {index} {row['first_name']} --> {row['country']}")
                continue
            
            try:
                row['creation_date'] = parser.parse(row['creation_date']).date()
            except Exception:
                error_messages.append(f"fila {index+2} Fecha de tarjeta inválida: {row['first_name']} {row['last_name']} --> {row['creation_date']}")
                continue

            if row['date_of_birth']:
                try:
                    row['date_of_birth'] = parser.parse(row['date_of_birth']).date()
                except Exception:
                    error_messages.append(f"fila {index+2} Fecha de nacimiento inválida: {row['first_name']} {row['last_name']} --> {row['date_of_birth']}")
                    continue
            
            try:
                client = Client.objects.get(phone=row['phone'] if row['phone'] else None, date_of_birth=row['date_of_birth'] if row['date_of_birth'] else None, country=country)
            except Client.DoesNotExist:
                client = Client.objects.create(
                    first_name = row['first_name'],
                    last_name = row['last_name'],
                    phone = row['phone'],
                    creation_date = row['creation_date'] if row['creation_date'] else None,
                    country = country,
                    date_of_birth = row['date_of_birth'] if row['date_of_birth'] else None,
                )

            try:
                row['card_num'] = int(row['card_num'])

                card = FidelityCard.objects.create(
                    card_num = row['card_num'],
                    created_at = row['creation_date'] if row['creation_date'] else None,
                    author = User.objects.get(id=1)
                )
            except Exception:
                error_messages.append(f"fila {index+2} tarjeta inválida: {row['first_name']} {row['last_name']} --> {row['card_num']}")
                card = FidelityCard.objects.get(pk=1)
                

            for env in envios:
                if(row[env[0]] or row[env[1]]):
                    try:
                        row[env[0]] = parser.parse(row[env[0]]).date()
                    except Exception:
                        continue

                    try:
                        row[env[1]] = float(row[env[1]].replace("$","").replace(",",""))
                    except Exception:
                        continue

                    datecut = date(2025, 5, 2)

                    if row[env[0]] < datecut:
                            
                        crated_at = datetime.combine(row[env[0]], time(11, 0, 0))

                        print(crated_at)
                        SendMoney.objects.create(
                            client = client,
                            amount = row[env[1]],
                            creation_date = crated_at,
                            country = country,
                            broker = Broker.objects.get(id=1),
                            fidelitycard = card,
                            author = User.objects.get(id=1),
                        )
                 
    for e in error_messages:
        print(e)

def clean_phone(x):
    if pd.notnull(x):
        return re.sub(r'\D', '', str(x))
    return ''

#python manage.py runscript clients.import_data
'''


        new_client, created = Client.objects.get_or_create(
        first_name = row['first_name'],
        last_name = row['last_name'],
        phone = row['phone'],
        defaults={
            'creation_date' : row['creation_date'],
            'card_date' : row['creation_date'],
            'country' : Country.objects.get(iso=row['country'].strip()),
            'date_of_birth' : row['date_of_birth'],
            }
        )
        
        if created:
            print(f"Created new client: {new_client}")
        else:
            print(f"Client already exists: {new_client}")


delete from clients_sendmoney;
delete from clients_sendpackage;
delete from clients_moneyorder;
delete from clients_comment;
delete from clients_document;
delete from tasks_taskfile;
delete from tasks_tasknote;
delete from tasks_task;
delete from clients_client;
COMMIT;

card_num	creation_date	first_name	last_name	phone	country	date_of_birth	H	I	J	K	L	M	N	O	P	Q	R	S	T	U	V	W	X	Y	Z	AA	AB	AC	AD	AE	AF	AG	AH	AI	AJ	AK	AL	AM	AN	AO	AP	AQ	AR	AS	AT	AU	AV	AW	AX	AY	AZ	BA	BB	BC	BD	BE	BF	BG	BH	BI	BJ	BK	BL	BM	BN	BO	BP	BQ	BR	BS	BT	BU
card_num,creation_date,first_name,last_name,phone,country,date_of_birth,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z,AA,AB,AC,AD,AE,AF,AG,AH,AI,AJ,AK,AL,AM,AN,AO,AP,AQ,AR,AS,AT,AU,AV,AW,AX,AY,AZ,BA,BB,BC,BD,BE,BF,BG,BH,BI,BJ,BK,BL,BM,BN,BO,BP,BQ,BR,BS,BT,BU

'''