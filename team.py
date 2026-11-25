def default_team():
 return [dict(nom=n,statut=s,groupes=3 if n in ('Akram','Igor') else 1,distance=True) for n,s in [('Akram','Coordination'),('Igor','Coordination'),('Giovanni Chierchia','Volontaire : 1 groupe'),('Selsabil-Belkis Bakhouche','Proposée'),('Amani','Proposée'),('Khaoula','Statut à vérifier'),('Secil Ercan','À contacter')]]
