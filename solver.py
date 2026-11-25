from collections import defaultdict
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix
ROOT=Path(__file__).parent
PROGRAM=['COURS 1','TD1','COURS 2','TD2-1','TD2-2','TD3','COURS 3','TD4-1','TD4-2','COURS 4','TD5-1','TD5-2','TP1','TD6-1','TD6-2']
CM=[0,2,6,9]
GROUPS={'E3ST/FD':[f'E3-{i}s-S2' for i in range(1,6)]+['E3-1t-S2','E3-2t-S2','E3-1d-S2'],'E3E':[f'E3-{i}e-S2' for i in range(1,7)]}

def cm_owner(owners, block, session):
 """Resolve a CM teacher; legacy scenarios assigned one teacher per block."""
 assignment=owners.get(block)
 return assignment.get(PROGRAM[session]) if isinstance(assignment,dict) else assignment

def cm_hours(owners, name):
 return 2*sum(cm_owner(owners,b,k)==name for b in GROUPS for k in CM)

def slots():
 d=pd.read_csv(ROOT/'creneaux.csv').sort_values(['date','heure']).reset_index(drop=True);d['id']=d.date+' '+d.heure.map(lambda x:f'{x:02d}:00');return d

class Model:
 def __init__(self):self.cost=[];self.rows=[];self.lo=[];self.hi=[]
 def var(self,c=0):self.cost.append(c);return len(self.cost)-1
 def con(self,t,lo=0,hi=0):self.rows.append(t);self.lo.append(lo);self.hi.append(hi)
 def solve(self,seconds):
  rr=[];cc=[];vv=[]
  for i,row in enumerate(self.rows):
   for j,v in row.items():
    if v:rr.append(i);cc.append(j);vv.append(v)
  a=coo_matrix((vv,(rr,cc)),shape=(len(self.rows),len(self.cost))).tocsc()
  return milp(np.array(self.cost),integrality=np.ones(len(self.cost)),bounds=Bounds(0,1),constraints=LinearConstraint(a,self.lo,self.hi),options={'time_limit':seconds,'mip_rel_gap':0.0})

def complete_team(rows):
 """Each placeholder is a distinct person with one group, never a confirmation."""
 team=[dict(r,groupes=int(r['groupes'])) for r in rows];missing=max(0,15-sum(t['groupes'] for t in team));used={t['nom'] for t in team}
 for i in range(1,missing+1):
  n=f'Renfort à recruter {i:02d}'
  while n in used:n+=' bis'
  used.add(n);team.append(dict(nom=n,statut='À recruter',groupes=1,distance=True))
 return team

def allocation_candidates(team,b3=None,blocked=(),available=None,owners=None,shared=False):
 """Enumerate block assignments satisfying necessary capacity bounds.
 Names of groups within a block are interchangeable in this model.
 """
 if sum(t['groupes'] for t in team)!=15:raise ValueError('Le total doit être de 15 groupes.')
 names=[t['nom'] for t in team]
 if len(set(names))!=len(names) or any(not n.strip() for n in names):raise ValueError('Noms vides ou en double.')
 positive=[t for t in team if t['groupes']>0]
 if b3 is not None and b3 not in [t['nom'] for t in positive]:raise ValueError('Référent B3 sans groupe disponible.')
 ordered=sorted(positive,key=lambda t:(-t['groupes'],not t['nom'].startswith('Renfort à recruter ')))
 b3choices=[b3] if b3 else [t['nom'] for t in sorted(positive,key=lambda t:(0 if t['groupes']>=3 else 1 if t['nom'].startswith('Renfort à recruter ') else 2,-t['groupes']))]
 d=slots() if available is None else available;d=d[~d.controle];blocked=set(blocked);blocks=list(GROUPS)
 caps={}
 for t in ordered:
  n=t['nom']
  for block in blocks:
   ss=d[d.bloc==block];usable=sum((n,r.id) not in blocked and (t['distance'] or not r.distance) for r in ss.itertuples())
   capacity=min(len(ss)-4,usable-sum(cm_owner(owners or {},block,k)==n for k in CM))
   caps[n,block]=max(0,capacity-10) if shared else max(0,capacity//11)
 for owner in b3choices:
  counts=[t['groupes']-int(t['nom']==owner) for t in ordered]
  def walk(i,left,assign):
   if i==len(ordered):
    if left==0:
     groups={b:iter(gs) for b,gs in GROUPS.items()};mapping={}
     for t,(x,y) in zip(ordered,assign):
      for block,k in zip(blocks,(x,y)):
       for _ in range(k):mapping[next(groups[block])]=t['nom']
     yield mapping,owner
    return
   t=ordered[i];n=t['nom'];k=counts[i];right=sum(counts[i:])-left
   lo=max(0,k-caps[n,blocks[1]],k-right);hi=min(k,caps[n,blocks[0]],left)
   choices=sorted(range(lo,hi+1),key=lambda x:(abs(2*x-k),-x if left>=right else x))
   for x in choices:
    yield from walk(i+1,left-x,assign+[(x,k-x)])
  yield from walk(0,len(GROUPS[blocks[0]]),[])

def allocate(team,b3=None,shared=False):
 """Initial preview. If impossible under standard slots, keep only a load preview."""
 candidate=next(allocation_candidates(team,b3,shared=shared),None)
 if candidate:return candidate
 # Preview only: preserve requested loads even when no schedule exists.
 positive=[t for t in team if t['groupes']>0]
 owner=b3 or max(positive,key=lambda t:t['groupes'])['nom']
 names=[t['nom'] for t in team for _ in range(t['groupes']-int(t['nom']==owner))]
 return dict(zip(sum(GROUPS.values(),[]),names)),owner

def search_planning(team,owners,b3=None,blocked=(),available=None,seconds=30,shared=False):
 import time
 start=time.monotonic();best=None;best_mapping=None;best_b3=None;best_cost=float('inf');tested=0;all_proven=True
 d=slots() if available is None else available;d=d[~d.controle]
 lower=sum(len(gs)*max(0,15-int((~d[d.bloc==b].distance).sum())) for b,gs in GROUPS.items())
 seen=set()
 for mapping,owner in allocation_candidates(team,b3,blocked,available,owners,shared):
  if time.monotonic()-start>=seconds:all_proven=False;break
  # Avoid equivalent attempts with interchangeable fictitious teachers.
  signature=tuple(sorted((n,b,sum(mapping[g]==n for g in gs)) for b,gs in GROUPS.items() for n in set(mapping.values()) if not n.startswith('Renfort à recruter ') or any(cm_owner(owners,bl,k)==n for bl in GROUPS for k in CM) or any(nn==n for nn,_ in blocked)))
  if signature in seen:continue
  seen.add(signature)
  remaining=seconds-(time.monotonic()-start)
  if remaining<=0:all_proven=False;break
  tested+=1
  df,msg=generate(team,owners,mapping,blocked,available,seconds=min(remaining,8),shared=shared)
  if df is None:
   if 'temps imparti' in msg or msg.startswith('Validation :'):all_proven=False
   continue
  cost=int(df.loc[df.Modalité=='Distance','Groupes'].str.split(' / ').str.len().sum())
  if cost<best_cost:best,best_mapping,best_b3,best_cost=df,mapping,owner,cost
  if cost==lower:return best,best_mapping,best_b3,f'Planning vérifié : minimum de distanciel démontré ({tested} affectation(s) testée(s)).'
  if 'démontré pour' not in msg:all_proven=False
 if best is not None:return best,best_mapping,best_b3,f'Planning vérifié ({tested} affectation(s) testée(s)). '+('Minimum de distanciel démontré.' if all_proven else 'Optimalité globale non démontrée.')
 if tested==0 and all_proven:return None,None,None,'Aucune répartition compatible avec les capacités des blocs et les disponibilités. En mode individuel, les A permettent un groupe par bloc E3 par référent. Envisager des créneaux supplémentaires ou un partage des séances entre enseignants.'
 return None,None,None,('Aucune affectation réalisable sous les contraintes retenues.' if all_proven else 'Aucun planning trouvé dans le temps imparti ; impossibilité non démontrée.')+f' ({tested} affectation(s) testée(s)).'

def generate(team,owners,mapping,blocked=(),available=None,seconds=20,shared=False):
 d=slots() if available is None else available.copy();d=d[~d.controle].sort_values(['date','heure']);blocked=set(blocked);people={t['nom']:t for t in team};m=Model();time=defaultdict(list);records={};seq={}
 for b,gg in GROUPS.items():
  ss=list(d[d.bloc==b].itertuples()); L=len(ss)
  if L<15:return None,f'{b} : moins de 15 créneaux.'
  for n in set(mapping[g] for g in gg):
   k=sum(mapping[g]==n for g in gg)
   if (10+k if shared else k*11)>L-4:return None,f'{n} : {k} groupes dans {b} nécessitent {k*11} créneaux TD/TP, mais seulement {L-4} après les CM. Modifier la répartition ou les créneaux.'
  for k in range(15):
   units=[' / '.join(gg)] if k in CM else ([' / '.join(g for g in gg if mapping[g]==n) for n in dict.fromkeys(mapping[g] for g in gg)] if shared and k!=12 else gg)
   for g in units:
    n=cm_owner(owners,b,k) if k in CM else mapping[g.split(' / ')[0]];vmap={}
    for j,s in enumerate(ss):
     if j<k or L-1-j<14-k:continue
     if (n,s.id) in blocked or (s.distance and (k in CM or k==12 or not people[n]['distance'])):continue
     v=m.var(len(g.split(' / '))*int(s.distance));vmap[j]=v;time[n,s.id].append(v);records[v]=(b,s,k,g,n)
    if not vmap:return None,f'Aucun créneau pour {n}, {g}, {PROGRAM[k]}.'
    m.con({v:1 for v in vmap.values()},1,1)
    for group in g.split(' / '):seq[group,k]=vmap
  for g in gg:
   for k in range(14):
    terms={v:j for j,v in seq[g,k+1].items()};terms.update({v:-j for j,v in seq[g,k].items()});m.con(terms,1,np.inf)
 for vs in time.values():m.con({v:1 for v in vs},0,1)
 res=m.solve(seconds)
 if res.x is None:return None,('Pas de solution pour cette répartition et ces contraintes.' if res.status==2 else 'Aucune solution trouvée dans le temps imparti ; impossibilité non démontrée.')
 rows=[]
 for v,(b,s,k,g,n) in records.items():
  if res.x[v]>.5:rows.append({'Date':s.date,'Début':f'{s.heure:02d}:00','Fin':f'{s.heure+2:02d}:00','Bloc':b,'Séance':PROGRAM[k],'Type':'CM' if k in CM else 'TP' if k==12 else 'TD','Groupes':g,'Intervenant':n,'Modalité':'Distance' if s.distance else 'Présentiel','Durée (h)':2,'Salle':''})
 df=pd.DataFrame(rows).sort_values(['Date','Début','Bloc','Groupes']).reset_index(drop=True)
 errors=validate(df,team,owners,mapping,blocked,available)
 if errors:return None,'Validation : '+ '; '.join(errors)
 return df,'Minimum de distanciel démontré pour cette répartition.' if res.status==0 else 'Planning réalisable vérifié ; optimalité non démontrée.'

def validate(df,team,owners,mapping,blocked=(),available=None):
 d=slots() if available is None else available;allowed={(r.bloc,r.date,f'{r.heure:02d}:00'):r.distance for r in d[~d.controle].itertuples()};people={t['nom']:t for t in team};seen=set();bygroup=defaultdict(list);issues=[];blocked=set(blocked)
 for r in df.to_dict('records'):
  b,g,n,k=r['Bloc'],r['Groupes'],r['Intervenant'],r['Séance'];when=r['Date']+' '+r['Début'];key=(b,r['Date'],r['Début']);dist=r['Modalité']=='Distance'
  if key not in allowed or allowed.get(key)!=dist:issues.append('Créneau interdit')
  if (n,when) in seen or (n,when) in blocked:issues.append('Conflit enseignant')
  seen.add((n,when))
  if n not in people or (dist and not people[n]['distance']):issues.append('Modalité interdite')
  if k not in PROGRAM:issues.append('Séance inconnue');continue
  i=PROGRAM.index(k);typ='CM' if i in CM else 'TP' if i==12 else 'TD'
  if r['Type']!=typ or r['Durée (h)']!=2:issues.append('Type ou durée incorrecte')
  if typ in ('CM','TP') and dist:issues.append('CM/TP à distance')
  if typ=='CM' and (cm_owner(owners,b,i)!=n or g.split(' / ')!=GROUPS[b]):issues.append('CM incorrect')
  if typ!='CM' and any(mapping.get(x)!=n for x in g.split(' / ')):issues.append('Référent incorrect')
  if typ!='CM' and ' / ' in g:issues.append('TD/TP mutualisé interdit')
  for gg in g.split(' / '):
   if gg not in GROUPS[b]:issues.append('Groupe hors bloc')
   bygroup[gg].append((when,k))
 for gg in mapping:
  q=sorted(bygroup[gg]);
  if [k for _,k in q]!=PROGRAM or len(set(w for w,_ in q))!=15:issues.append('Couverture/ordre : '+gg)
 return sorted(set(issues))


def partial_planning(team,owners,b3=None,blocked=(),available=None,seconds=20):
 """Fixed balanced reference assignment; maximize covered student sessions, then presence."""
 d=slots() if available is None else available.copy();d=d[~d.controle].sort_values(['date','heure']);blocked=set(blocked);people={t['nom']:t for t in team}
 positive=sorted([t for t in team if t['groupes']>0],key=lambda t:-t['groupes']);owner=b3 or positive[0]['nom']
 remaining={b:list(gs) for b,gs in GROUPS.items()};mapping={}
 for t in positive:
  n=t['nom'];used=defaultdict(int)
  for _ in range(t['groupes']-int(n==owner)):
   b=max((b for b in remaining if remaining[b]),key=lambda b:(-used[b],len(remaining[b])))
   mapping[remaining[b].pop(0)]=n;used[b]+=1
 m=Model();times=defaultdict(list);records={};seq={}
 for b,gg in GROUPS.items():
  ss=list(d[d.bloc==b].itertuples());L=len(ss)
  for k in range(len(PROGRAM)):
   for g in ([' / '.join(gg)] if k in CM else gg):
    n=cm_owner(owners,b,k) if k in CM else mapping[g];vs={};weight=len(g.split(' / '))
    for j,t in enumerate(ss):
     if (n,t.id) in blocked or (t.distance and (k in CM or k==12 or not people[n]['distance'])):continue
     v=m.var(weight*(-1000+int(t.distance)));vs[j]=v;times[n,t.id].append(v);records[v]=(b,t,k,g,n)
    m.con({v:1 for v in vs.values()},0,1)
    for group in g.split(' / '):seq[group,k]=vs
  # For any two selected sessions, enforce chronological order. Missing sessions remain explicit gaps.
  for g in gg:
   for k in range(len(PROGRAM)):
    for l in range(k+1,len(PROGRAM)):
     a,z=seq[g,k],seq[g,l]
     if not a or not z:continue
     terms={v:j+L for j,v in a.items()};terms.update({v:L-j for j,v in z.items()});m.con(terms,-np.inf,2*L-1)
 for vs in times.values():m.con({v:1 for v in vs},0,1)
 if not records:return None,mapping,owner,'Aucun créneau utilisable.'
 res=m.solve(seconds)
 if res.x is None:return None,mapping,owner,'Aucun planning partiel trouvé dans le temps imparti.'
 rows=[]
 for v,(b,t,k,g,n) in records.items():
  if res.x[v]>.5:rows.append({'Date':t.date,'Début':f'{t.heure:02d}:00','Fin':f'{t.heure+2:02d}:00','Bloc':b,'Séance':PROGRAM[k],'Type':'CM' if k in CM else 'TP' if k==12 else 'TD','Groupes':g,'Intervenant':n,'Modalité':'Distance' if t.distance else 'Présentiel','Durée (h)':2,'Salle':''})
 if not rows:return None,mapping,owner,'Aucune séance affectée.'
 df=pd.DataFrame(rows).sort_values(['Date','Début','Bloc','Groupes']).reset_index(drop=True)
 # Full validator checks the same hard constraints; only incomplete coverage is permitted.
 errors=[e for e in validate(df,team,owners,mapping,blocked,available) if not e.startswith('Couverture/ordre : ')]
 for g in mapping:
  q=df[df.Groupes.str.split(' / ').apply(lambda gs:g in gs)]
  ix=[PROGRAM.index(k) for k in q.Séance]
  if ix!=sorted(set(ix)) or q.duplicated(['Date','Début']).any():errors.append('Ordre/conflit groupe : '+g)
 if errors:return None,mapping,owner,'Validation : '+'; '.join(errors)
 return df,mapping,owner,'Proposition partielle sur une affectation équilibrée. Les séances manquantes restent à négocier ; optimalité globale non démontrée.'
