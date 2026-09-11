import pandas as pd
from datetime import date, datetime, time
from clients.models import Client, Country, SendMoney, FidelityCard, Broker
from django.contrib.auth import get_user_model
import numpy as np
import re
from dateutil import parser
from django.db.models import CharField, Value
from django.db.models.functions import Concat


def run():
    User = get_user_model()
    #df = pd.read_csv('/home/william/Downloads/INTERMEX_extra.csv', sep='|')
    df = pd.read_csv('/home/william/Downloads/VIAMERICAS_extra.csv', sep='|')
    print(f"date|sender|country|amount")

    for index, row in df.iterrows():
        full_name = row['sender']
        if pd.isna(row['sender']):
            continue
        
        if not pd.isna(row['last_name']):
            full_name = row['sender'].strip() + ' ' + row['last_name'].strip()
        
        client = Client.objects.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name', output_field=CharField())
        ).filter(full_name__icontains = full_name.strip())

      
        if not pd.isna(row['country']):
            match row['country'].strip():
                case 'HO':
                    row['country'] = 'HN'
                case 'GU':
                    row['country'] = 'GT'
                case 'SA':
                    row['country'] = 'SV'

            country = Country.objects.get(iso=row['country'].strip())
        #else:   
         #   country = client.first().country

        amount = row['amount']
        if "(" in row['amount']:
            amount = amount.replace('(','').replace(')','')
            amount = float(amount) * -1

        if float(amount) == 0:
            continue
        
        date_envio= parser.parse(row['date']).date()
        crated_at = datetime.combine(date_envio, time(11, 0, 0))

        #if client.count() != 1 and pd.isna(row['country']):
        #    print(f"{row['sender']}|{row['last_name']}|{client.count()}")
        #    print(row['country'])

        #if client.count() != 1 :
        #    print(f"|{row['sender']}|{row['last_name']}|{client.count()}")
        
        #client = client.first()
        #print()
        '''
        if client.count() == 0 and not pd.isna(row['last_name']):            
            client = Client.objects.create(
                first_name = row['sender'].strip().upper(),
                last_name = row['last_name'].strip().upper(),
                country = country,
                creation_date = crated_at,
            )
        elif client.count() > 0:
        '''
        
        broker = Broker.objects.get(broker_name=row['broker'].capitalize())
        fidelitycard = FidelityCard.objects.get(id=1)        
        author = User.objects.get(id=1)
        
        SendMoney.objects.create(
                client = client.first(),
                amount = amount,
                creation_date = crated_at,
                country = client.first().country,
                broker = broker,
                fidelitycard = fidelitycard,
                author = author,
            )
        