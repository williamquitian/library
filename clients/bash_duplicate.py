import pandas as pd
from datetime import date, datetime, time
from clients.models import Client, Country, SendMoney, FidelityCard, Broker, Document, Comment
from django.contrib.auth import get_user_model
import numpy as np
from django.db.models.functions import Concat
from django.db.models import CharField, Value
import re
from dateutil import parser

def run():
    list_client = [
        'JUAN CARLOS XOL CAAL',
        'JUAN CHUB CHOC',
        'JUAN CUZ CHOC',
        'JUAN DIEGO LOPEZ GARCIA',
        'JUAN JOSE APARICIO DUENAS',
        'JUAN OLIVARES GONZALEZ',
        'JUAN PEC XOL',
        'JUANA MELCHOR TAPERIA',
        'JULIO ELIAS ICHICH JUC',
        'LUCIELA JIMENEZ RUIZ',
        'LUIS CHUB CHUB',
        'LUIS ORLANDO QUINTEROS',
        'MANUEL ENRIQUE CASTILLO MENDEZ',
        'MANUEL PERDOMO PERDOMO',
        'MANUEL TZIBOY XOL',
        'MARCELINO TZIB SAM',
        'MARCIAL GARCIA ESPINOZA',
        'MARCIAL TORQUEMADA TREJO',
        'MARIA ALBERTINA IXPATA DE CHAPAZ',
        'MARIO CORTEZ MANUEL',
        'MARIO IVAN FLORES MENDEZ',
        'MARIO SACUL POP',
        'MARVIN DIONEL COC PACAY',
        'MARVIN ROGELIO SUB PAAU',
        'MIGUEL CALO ARNULFO',
        'NERI YOVANI CAHUEC ACOJ',
        'NESTOR EUGENIO TIUL ICAL',
        'OLEGARIO MORENTE MELCHOR',
        'OSCAR CAN CHOC',
        'OSCAR CUCUL XOL',
        'OSCAR HUMBERTO CAZ YAT',
        'OTTO GONZALO LUC POP',
        'PEDRO CUCUL CHOC',
        'PEDRO J MAHECHA',
        'PEDRO ROLANDO PEDRO BALTAZAR',
        'RAFAEL XITUMUL LAJUJ',
        'RAMIREZ RONI RAMIREZ JUAN',
        'RAUL ESTUARDO QUIB XICOL',
        'RAUL FERNANDO CAAL XOL',
        'RICARDO RUIZ CAMAJA',
        'ROBERTO TIUL XO',
        'RODOLFO GONZALEZ SANCHEZ',
        'ROLANDO TIUL QUIB',
        'SALVADOR GARCIA ZERMENO',
        'SANTIAGO CHO TZIB',
        'SANTIAGO CUCUL CHOC',
        'SANTIAGO ENRIQUEZ MOLINA',
        'SANTOS CHANCHAVAC TZUN',
        'SANTOS DOMINGO JIMENEZ',
        'SANTOS REYES MELCHOR',
        'SAQUEO ICHICH CUZ',
        'SEBASTIAN COC POP',
        'SERGIO ABRAHAM CAAL MAAS',
        'SILVERIO TIQUIRAM LOPEZ',
        'SIMON PEDRO PEC POP',
        'TITO VENJAMIN CRUZ LOPEZ',
        'TOMAS SACUL CHEN',
        'URBANO ZARATE MORALES',
        'WILLIAM RUBEN FLORES DIAZ']

    #name = input("Please enter your client name: ")
    for name in list_client:
        clients = Client.objects.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name', output_field=CharField())
        ).filter(full_name=name)

        for cl in clients:
            print(f"{cl.id} | {cl.first_name}| {cl.last_name} | {cl.phone} | {cl.date_of_birth} | {cl.country} |")
            if cl.sendmoney.count() > 0:
                print(f"Send Money | {cl.sendmoney.count()}")
            if cl.sendpackage.count() > 0:
                print(f"Send package | {cl.sendpackage.count()}")
            if cl.moneyorder.count() > 0:
                print(f"Money Order | {cl.moneyorder.count()}")
            if cl.documents.count() > 0:
                print(f"Documents | {cl.documents.count()}")
            if cl.comments.count() > 0:
                print(f"Comments | {cl.comments.count()}")

        keepID = input("Please enter ID to keep: ")

        keepClient = Client.objects.get(id=int(keepID))

        for cl in clients:
            if int(keepID) != cl.id:
                toDelete = Client.objects.get(id=cl.id)
                SendMoney.objects.filter(client=toDelete).update(client=keepClient)
                Document.objects.filter(client=toDelete).update(client=keepClient)
                Comment.objects.filter(client=toDelete).update(client=keepClient)
                print(f"{cl.id} | {cl.first_name}| {cl.last_name} | {cl.phone} | {cl.date_of_birth} | {cl.country} |")
                if cl.sendmoney.count() > 0:
                    print(f"Send Money | {cl.sendmoney.count()}")
                if cl.sendpackage.count() > 0:
                    print(f"Send package | {cl.sendpackage.count()}")
                if cl.moneyorder.count() > 0:
                    print(f"Money Order | {cl.moneyorder.count()}")
                if cl.documents.count() > 0:
                    print(f"Documents | {cl.documents.count()}")
                if cl.comments.count() > 0:
                    print(f"Comments | {cl.comments.count()}")
                toDelete.delete()
                print("************* Deleted *****************")
                print("=======================================")

        clients = Client.objects.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name', output_field=CharField())
        ).filter(full_name=name)

        for cl in clients:
            print(f"{cl.id} | {cl.first_name}| {cl.last_name} | {cl.phone} | {cl.date_of_birth} | {cl.country} |")
            if cl.sendmoney.count() > 0:
                print(f"Send Money | {cl.sendmoney.count()}")
            if cl.sendpackage.count() > 0:
                print(f"Send package | {cl.sendpackage.count()}")
            if cl.moneyorder.count() > 0:
                print(f"Money Order | {cl.moneyorder.count()}")
            if cl.documents.count() > 0:
                print(f"Documents | {cl.documents.count()}")
            if cl.comments.count() > 0:
                print(f"Comments | {cl.comments.count()}")