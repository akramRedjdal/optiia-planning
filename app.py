import json
from pathlib import Path
import pandas as pd
import streamlit as st
from solver import CM, cm_owner, cm_hours, generate, validate, slots, GROUPS, PROGRAM, complete_team, allocate, search_planning, partial_planning
from team import default_team
import persistence

st.set_page_config(page_title='Planning des enseignements',layout='wide')
st.title('Planning des enseignements 2026–2027')
st.caption('Unité : Optimisation et introduction IA')
if 'result' not in st.session_state:st.session_state.result=None
if 'team_seed' not in st.session_state:
 try: saved=persistence.load()
 except Exception as e: saved={};st.warning(f'Sauvegarde locale illisible : {e}')
 st.session_state.team_seed=saved.get('team',default_team());st.session_state.imported=saved
 if saved.get('planning') is not None:
  st.session_state.result=pd.DataFrame(saved['planning']);st.session_state.chosen_mapping=saved['mapping'];st.session_state.chosen_b3=saved['chosen_b3'];st.session_state.diagnostic=saved['diagnostic'];st.session_state.fingerprint=saved['fingerprint']
if 'input_version' not in st.session_state:st.session_state.input_version=0
with st.sidebar:
 st.header('Sauvegarde et reprise')
 st.caption('Vos paramètres sont enregistrés automatiquement sur cet ordinateur.')
 if st.button('Effacer la sauvegarde et rétablir les valeurs par défaut'):
  persistence.reset();st.session_state.team_seed=default_team();st.session_state.imported={};st.session_state.input_version+=1;st.session_state.result=None;st.session_state.pop('fingerprint',None);st.session_state.pop('approved',None);st.rerun()
 up=st.file_uploader('Importer des paramètres (fichier JSON)',type='json')
 if up and st.button('Charger les paramètres'):
  try:
   data=json.load(up);st.session_state.team_seed=data['team'];st.session_state.imported=data;st.session_state.input_version+=1;st.session_state.result=None;st.session_state.pop('fingerprint',None);st.session_state.pop('approved',None);st.rerun()
  except Exception as e:st.error(str(e))
 st.caption('Le planning reste sur cet ordinateur tant que vous ne le publiez pas. Les personnes à recruter ne sont pas encore engagées.')
imp=st.session_state.get('imported',{});ver=st.session_state.input_version
st.subheader('Équipe enseignante et répartition des groupes')
a,b,c,d=st.columns(4);a.metric('Nombre total de groupes',15);b.metric('Groupes E3 à planifier',14);c.metric('Heures prévues par groupe E3','30 h');d.metric('TD/TP par groupe','22 h')
st.caption('8 E3ST/FD · 6 E3E · 1 B3 indépendant. B3 : 22 h TD/TP réservées à titre d’hypothèse, CM et créneaux à confirmer. 324 h de service E3 = 308 h TD/TP + 16 h CM mutualisés, hors examens et HETD.')
st.write('Indiquez le nombre de groupes prévu pour chaque enseignant. Pour les groupes restants, le calcul ajoute des enseignants à recruter, à raison d’un groupe chacun.')
ed=st.data_editor(pd.DataFrame(st.session_state.team_seed),num_rows='dynamic',hide_index=True,key=f'team_{ver}',use_container_width=True,column_order=['nom','statut','groupes','distance'],column_config={'nom':st.column_config.TextColumn('Intervenant',required=True),'statut':st.column_config.SelectboxColumn('Statut',options=['Coordination','Confirmé','Volontaire : 1 groupe','Proposée','Statut à vérifier','À contacter','À recruter'],required=True),'groupes':st.column_config.NumberColumn('Groupes prévus',min_value=0,max_value=15,step=1,required=True),'distance':st.column_config.CheckboxColumn('Peut enseigner à distance',default=True)})
rows=ed.fillna({'nom':'','statut':'À recruter','groupes':0,'distance':True}).to_dict('records')
for t in rows:t['nom']=str(t['nom']).strip();t['groupes']=int(t['groupes'])
requested=sum(t['groupes'] for t in rows);team=complete_team(rows);positive=[t for t in team if t['groupes']>0];known=[t for t in rows if t['groupes']>0];firm=sum(t['groupes'] for t in known if t['statut'] in ['Confirmé','Coordination','Volontaire : 1 groupe']);missing=max(0,15-requested)
a,b,c,d=st.columns(4);a.metric('Enseignants TD/TP, recrutements inclus',len(positive),delta=f'{len(positive)-15:+d} par rapport à un groupe par personne' if len(positive)!=15 else None,delta_color='off');b.metric('Groupes déjà attribués',f'{requested}/15');c.metric('Enseignants à recruter',missing);d.metric('Heures TD/TP déjà attribuées',f'{22*requested} h')
st.caption(f'Groupes attribués à des personnes nommées : {requested}, dont {firm} sous statut coordination/confirmé/volontaire (les charges de coordination restent des hypothèses). Référence théorique : 330 h TD/TP pour 15 groupes, dont 22 h B3 non planifiées.')
if requested>15:st.error('Trop de groupes attribués : réduisez les charges.');st.stop()
if len({t['nom'] for t in rows})!=len(rows) or any(not t['nom'] for t in rows):st.error('Renseignez des noms uniques, non vides.');st.stop()
if any(t['nom']=='Giovanni Chierchia' and t['groupes']>1 for t in rows):st.error('Giovanni a proposé un seul groupe. Confirmez un autre engagement avant de changer sa charge.');st.stop()
if not team:st.stop()
names=[t['nom'] for t in team];owners={}
st.subheader('Répartition des cours magistraux')
st.caption('Pour chaque bloc, choisissez qui assure les cours 1 et 2, puis les cours 3 et 4. Vous pouvez inverser Akram et Igor selon le bloc.')
for col,block in zip(st.columns(2),GROUPS):
 col.write(block)
 owners[block]={}
 for label,sessions,default in [('Cours 1 et 2',CM[:2],'Akram'),('Cours 3 et 4',CM[2:],'Igor')]:
  initial=cm_owner(imp.get('owners',{}),block,sessions[0]) or default
  teacher=col.selectbox(f'{label} — {block}',names,index=names.index(initial) if initial in names else 0,key=f'cm_{block}_{sessions[0]}_{ver}')
  for k in sessions:owners[block][PROGRAM[k]]=teacher
b3opts=['Automatique']+[t['nom'] for t in positive];initial=imp.get('b3','Automatique');b3choice=st.selectbox('Enseignant prévu pour le groupe B3',b3opts,index=b3opts.index(initial) if initial in b3opts else 0,key=f'b3_{ver}')
shared=False
mapping,b3=allocate(team,None if b3choice=='Automatique' else b3choice,shared=shared)
st.subheader('Créneaux de cours et disponibilités')
all_slots=pd.read_csv(Path(__file__).parent/'creneaux_toutes_unites.csv')
base=slots()
imp=st.session_state.get('imported',{})
version=ver
st.caption('Source : grilles S2 2026–2027 E3ST, E3FD, E3E. Les lettres B–F sont réservées à d’autres unités, jamais libres par défaut. Les cases non lettrées ne sont pas interprétées comme disponibles.')
with st.expander('Consulter le calendrier des unités A à F',expanded=False):
    c1,c2,c3=st.columns(3)
    fil=c1.selectbox('Filière',['E3ST','E3FD','E3E'])
    week=c2.selectbox('Semaine',[9,10,11,12,13,14,15,16,17,18])
    letters=c3.multiselect('Unités affichées',list('ABCDEF'),default=['A'])
    unit_names={'A':'Optimisation et introduction IA','B':'Bases de données relationnelles','C':'IA, Deep learning et applications' if fil=='E3FD' else 'Contrôle des systèmes dynamiques','D':'Data Sciences et applications' if fil=='E3FD' else 'Systèmes électroniques à base de microprocesseurs','E':'Systèmes d’exploitation' if fil=='E3FD' else 'Bloc E : options (dont Systèmes d’exploitation)','F':'Programmation C++, projet et jeux' if fil=='E3FD' else 'Bloc F : options (dont IA et Deep Learning)'}
    start=pd.Timestamp('2027-03-01')+pd.Timedelta(weeks=week-9)
    days=[(start+pd.Timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6)]
    view=all_slots[(all_slots.filiere==fil)&(all_slots.semaine==week)&all_slots.unite.isin(letters)]
    grid=view.pivot(index='heure',columns='date',values='unite').reindex(index=[8,10,13,15,17],columns=days).fillna('—')
    grid.index=[f'{h:02d}h–{h+2:02d}h' for h in grid.index];grid.columns=[f'{j} {d[8:10]}/{d[5:7]}' for j,d in zip(['Lun','Mar','Mer','Jeu','Ven · distance','Sam'],days)]
    palette={'A':'#b9dfbc','B':'#c5ddf5','C':'#f5d5a8','D':'#e2d1ef','E':'#f5e6a5','F':'#f3c8ce'}
    st.dataframe(grid.style.apply(lambda col:[f'background-color:{palette[v]};color:#222' if v in palette else '' for v in col]),use_container_width=True)
    st.caption(' · '.join(f'{k} : {unit_names[k]}' for k in letters))
    if week in [14,15]: st.info('Vacances scolaires.')
    if week==18: st.info('Semaine de contrôles : aucun cours ne sera planifié sur ces créneaux.')
    st.download_button('Exporter les créneaux A–F des 3 filières',all_slots.to_csv(index=False,sep=';').encode('utf-8-sig'),'creneaux_A_F.csv','text/csv')
with st.expander('Retirer des créneaux de l’unité A'):
    st.caption('Les créneaux sélectionnés seront exclus du calcul pour le bloc indiqué. Désélectionnez un créneau pour le rétablir.')
    base_keys=base.bloc+' | '+base.id
    removable=base_keys[~base.controle].tolist()
    excluded_a=st.multiselect('Créneaux A à retirer du planning',removable,default=[v for v in imp.get('excluded_a',[]) if v in removable],key=f'excluded_a_{version}')
    retained_base=base[~base_keys.isin(excluded_a)]
    if excluded_a: st.info(f'{len(excluded_a)} créneau(x) A exclu(s) du calcul.')
with st.expander('Essayer des créneaux d’autres unités (à négocier)'):
    st.warning('Simulation seulement : aucun créneau B–F ne peut être considéré acquis. Pour E3ST/FD, seules les positions communes aux deux grilles et de même lettre sont proposées. Pas de déplacement automatique des autres unités.')
    x=all_slots[(all_slots.unite!='A')&(~all_slots.controle)].copy()
    common=x[x.filiere=='E3ST'].merge(x[x.filiere=='E3FD'],on=['date','heure','unite','distance','controle'],suffixes=('','_fd'))
    candidates=pd.concat([common.assign(bloc='E3ST/FD'),x[x.filiere=='E3E'].assign(bloc='E3E')],ignore_index=True)
    candidates['id']=candidates.date+' '+candidates.heure.map(lambda h:f'{h:02d}:00')
    candidates['label']=candidates.bloc+' | '+candidates.id+' | '+candidates.unite+candidates.distance.map({True:' | distance',False:' | présentiel'})
    options=candidates.label.tolist()
    extras=st.multiselect('Créneaux à essayer en complément de ceux de l’unité A',options,default=[v for v in imp.get('extras',[]) if v in options],key=f'extras_{version}')
    extra_rows=candidates[candidates.label.isin(extras)][base.columns]
    available=pd.concat([retained_base,extra_rows],ignore_index=True).sort_values(['date','heure']).reset_index(drop=True)
    if extras: st.info(f'{len(extras)} créneau(x) à négocier ajouté(s) au calcul. Le planning ne peut pas être publié avec ces créneaux.')
    else: st.caption('Le calcul utilise uniquement les créneaux A que vous avez conservés.')

with st.expander('Indiquer les indisponibilités des enseignants'):
 times=sorted(available[~available.controle].id.unique());blocked=[]
 for n in names:
  init=[t for nn,t in imp.get('blocked',[]) if nn==n and t in times]
  for t in st.multiselect(n,times,default=init,key=f'blocked_{n}_{ver}'):blocked.append((n,t))
with st.expander('Vérifier l’ordre des séances et les créneaux utilisés pour le calcul'):
 st.write(' → '.join(PROGRAM));st.caption('L’ordre des séances reste à confirmer. Les cours magistraux et le TP ont lieu en présentiel. Les 10 séances de TD sont organisées séparément pour chaque groupe. Les contrôles ne sont pas planifiés.')
 st.dataframe(available.drop(columns='id'),hide_index=True,use_container_width=True)
settings={'team':rows,'owners':owners,'blocked':blocked,'extras':extras,'excluded_a':excluded_a,'b3':b3choice,'shared':shared};fp=json.dumps(settings,sort_keys=True,ensure_ascii=False)
def autosave():
 data=dict(settings)
 if st.session_state.get('fingerprint')==fp and st.session_state.result is not None:
  data.update(planning=st.session_state.result.to_dict('records'),mapping=st.session_state.chosen_mapping,chosen_b3=st.session_state.chosen_b3,diagnostic=st.session_state.diagnostic,fingerprint=fp)
 try:persistence.save(data);st.sidebar.caption('Paramètres enregistrés sur cet ordinateur.')
 except Exception as e:st.sidebar.error(f'Sauvegarde impossible : {e}')
autosave()
st.download_button('Télécharger les paramètres (JSON)',json.dumps(settings,ensure_ascii=False,indent=2),'scenario.json','application/json')
st.divider();st.subheader('Calcul du planning')
if st.button('Calculer le planning',type='primary'):
 with st.spinner('Calcul du planning en cours…'):
  result,chosen,chosen_b3,msg=search_planning(team,owners,None if b3choice=='Automatique' else b3choice,blocked,available,seconds=15,shared=False)
  if result is None:
   result,chosen,chosen_b3,msg=partial_planning(team,owners,None if b3choice=='Automatique' else b3choice,blocked,available,seconds=15)
 st.session_state.result=result;st.session_state.chosen_mapping=chosen;st.session_state.chosen_b3=chosen_b3;st.session_state.diagnostic=msg;st.session_state.fingerprint=fp;st.session_state.pop('approved',None)
 autosave()
if st.session_state.get('fingerprint')==fp and st.session_state.result is not None:
 mapping=st.session_state.chosen_mapping;b3=st.session_state.chosen_b3
charge=[]
for t in team:
 n=t['nom'];gs=[g for g,v in mapping.items() if v==n];cm=cm_hours(owners,n);h=(sum(20+2*sum(g in GROUPS[bl] for g in gs) for bl in GROUPS if any(g in GROUPS[bl] for g in gs)) if shared else 22*len(gs));reserve=22*int(n==b3)
 if h or cm or reserve:charge.append({'Intervenant':n,'Statut':t['statut'],'Groupes E3':len(gs),'B3 réservé':int(n==b3),'TD/TP E3 (h)':h,'Volume groupes E3 (h)':22*len(gs),'CM E3 (h)':cm,'Total E3 (h)':h+cm,'Réserve B3 (h)':reserve,'Groupes proposés':', '.join(gs+(['B3'] if reserve else []))})
charges=pd.DataFrame(charge);st.metric('Enseignants prévus, cours magistraux et recrutements inclus',len(charges));st.dataframe(charges,hide_index=True,use_container_width=True)
st.caption('Charges de service estimées et groupes proposés (le volume groupes compte chaque groupe séparément). Après calcul, le tableau reflète la répartition retenue. B3 reste une réservation sans dates.')
if st.session_state.get('fingerprint')!=fp:
 st.info('La répartition ci-dessus tient compte de vos paramètres. Cliquez sur « Calculer le planning » pour attribuer des dates aux séances.');st.stop()
if st.session_state.result is None:st.warning(st.session_state.diagnostic);st.caption('Le nombre de personnes ne garantit pas la faisabilité horaire. Les charges saisies restent conservées. Vous pouvez tester des créneaux supplémentaires ou revoir le principe du référent unique.');st.stop()
df=st.session_state.result.copy();st.info(st.session_state.diagnostic)
coverage={g:int(df.Groupes.str.split(' / ').apply(lambda gs:g in gs).sum()) for g in mapping}
partial=any(v!=15 for v in coverage.values())
if partial:
 st.warning('Planning partiel : séances manquantes à compléter. Publication interdite.')
 st.dataframe(pd.DataFrame([{'Groupe':g,'Séances affectées':v,'Heures restantes':2*(15-v),'Séances manquantes':', '.join(k for k in PROGRAM if k not in set(df.loc[df.Groupes.str.split(' / ').apply(lambda gs:g in gs),'Séance']))} for g,v in coverage.items()]),hide_index=True)
w=df.Groupes.str.split(' / ').str.len()*df['Durée (h)'];dist=int(w[df.Modalité=='Distance'].sum());tot=int(w.sum());a,b,c,d=st.columns(4);a.metric('Groupes E3 au planning complet',f'{sum(v==15 for v in coverage.values())}/14');b.metric('Heures de service E3',f'{df["Durée (h)"].sum()} h');c.metric('Part des heures en présentiel',f'{100*(tot-dist)/tot:.1f} %');d.metric('Heures à distance par groupe E3',f'{dist/14:.1f} h')
with st.expander('Vérifier les créneaux de l’unité A utilisés ou non',expanded=False):
 use={(r.Bloc,r.Date,r.Début) for r in df.itertuples()};review=base[~base.controle].copy();review['Statut']=['Retiré du calcul' if r.bloc+' | '+r.id in excluded_a else 'Utilisé' if (r.bloc,r.date,f'{r.heure:02d}:00') in use else 'Non utilisé' for r in review.itertuples()];st.dataframe(review.drop(columns='id'),hide_index=True,use_container_width=True);st.caption('Un créneau retiré ou non utilisé n’est pas automatiquement rendu à la scolarité.')
f1,f2,f3=st.columns(3);block=f1.selectbox('Bloc de formation',['Tous']+list(GROUPS));who=f2.selectbox('Enseignant',['Tous']+sorted(df.Intervenant.unique()));group=f3.selectbox('Groupe',['Tous']+sum(GROUPS.values(),[]));view=df.copy()
if block!='Tous':view=view[view.Bloc==block]
if who!='Tous':view=view[view.Intervenant==who]
if group!='Tous':view=view[view.Groupes.str.split(' / ').apply(lambda gs:group in gs)]
st.dataframe(view,hide_index=True,use_container_width=True,height=460)
st.download_button('Télécharger le planning (CSV)',df.to_csv(index=False,sep=';').encode('utf-8-sig'),'planning_E3_provisoire.csv','text/csv')
st.divider();st.subheader('Publier le planning dans Google Sheets')
used=set(df.Intervenant);tentative=[t['nom'] for t in team if t['nom'] in used and t['statut'] not in ['Confirmé']]
if partial:st.warning('Publication bloquée : planning incomplet.')
if tentative:st.warning('Publication bloquée : confirmez les statuts des personnes affectées au planning, y compris les coordinateurs. '+', '.join(tentative))
if extras:st.warning('Publication bloquée : créneaux supplémentaires hypothétiques.')

try:cfg=st.secrets.get('sheets',{});service=st.secrets.get('gcp_service_account',{})
except Exception:cfg={};service={}
if not cfg.get('official_id') or not service:st.info('Google Sheets non connecté. Voir README et .streamlit/secrets.example.toml. Le CSV reste disponible.');st.stop()
st.caption('La publication remplace le contenu de l’onglet Planning E3. Elle ne comprend pas le groupe B3, les contrôles, les salles ni le décompte en heures équivalent TD (HETD).')
approved=st.checkbox('Je valide le planning E3 et autorise le remplacement du contenu de l’onglet Planning E3.',key='approved')
if st.button('Publier dans Google Sheets',disabled=bool(tentative or extras or partial or not approved)):
 errors=validate(df,team,owners,mapping,blocked,available)
 if errors:st.error('; '.join(errors))
 else:
  try:
   from sheets import publish
   url=publish(df,dict(service),cfg['official_id']);st.success('Planning publié.');st.link_button('Ouvrir le planning dans Google Sheets',url)
  except Exception as e:st.error(f'Publication non confirmée : {e}')
