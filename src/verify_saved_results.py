"""Independent read-only cross-check of the available Zara project's saved CSV outputs.
Does not require Pyomo or modify the original data.
"""
from pathlib import Path
from collections import defaultdict, Counter
import csv, math, json
ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/"data"
RESULTS=ROOT/"results"
INPUT_NAMES={"stores.csv","articles.csv","warehouse.csv","store_article_size.csv","saturation_segments.csv","model_settings.csv"}
def rows(name):
    folder=DATA if name in INPUT_NAMES else RESULTS
    with (folder/name).open(newline="",encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))
prices={r['article']:float(r['selling_price_eur']) for r in rows('articles.csv')}
warehouse={(r['article'],r['size']):(int(r['warehouse_stock_units']),float(r['retention_value_eur_per_unit'])) for r in rows('warehouse.csv')}
stores={r['store']:int(r['shipment_capacity_units']) for r in rows('stores.csv')}
stock={(r['store'],r['article'],r['size']):(int(r['initial_store_inventory_units']),int(r['forecast_demand_units'])) for r in rows('store_article_size.csv')}
segs=defaultdict(list)
for r in rows('saturation_segments.csv'):segs[(r['store'],r['article'],r['size'])].append((int(r['segment']),float(r['slope']),float(r['intercept'])))
alloc={}
for r in rows('revised_allocation.csv'):
    k=(r['store'],r['article'],r['size']);assert k not in alloc
    alloc[k]={v:float(r[v]) for v in ['initial_inventory','shipped_units','available_inventory','expected_sales','partial_exposure','full_exposure']}
retained={(r['article'],r['size']):int(r['retained_units']) for r in rows('revised_remaining_stock.csv')}
errors=[]
def check(cond,msg):
    if not cond:errors.append(msg)
for k,r in alloc.items():
    i,a,s=k
    b,d=stock[k]
    check(abs(r['initial_inventory']-b)<1e-7,f'initial mismatch {k}')
    check(abs(r['available_inventory']-(b+r['shipped_units']))<1e-7,f'available mismatch {k}')
    check(r['expected_sales']<=r['available_inventory']+1e-6,f'physical limit {k}')
    check(r['expected_sales']<=d+1e-6,f'demand limit {k}')
    check(abs(r['shipped_units']-round(r['shipped_units']))<1e-6,f'noninteger shipment {k}')
    check(len(segs[k])==4,f'segments count {k}')
    cap=min(a0*r['available_inventory']+b0 for _,a0,b0 in segs[k])
    factor=.6*r['partial_exposure']+.4*r['full_exposure']
    check(r['expected_sales']<=factor*cap+1e-6,f'exposure saturation limit {k} ({r["expected_sales"]}, max {factor*cap})')
    check(r['partial_exposure']>=r['full_exposure'],f'binary hierarchy {k}')
exp_count=Counter()
for i in stores:
    total=sum(alloc[i,a,s]['shipped_units'] for a in prices for s in ['XS','S','M','L'])
    check(total<=stores[i]+1e-6,f'capacity violated {i}')
    check(abs(total-stores[i])<1e-6,f'capacity not binding {i}: {total} vs {stores[i]}')
    for a in prices:
        u=alloc[i,a,'XS']['partial_exposure'];v=alloc[i,a,'XS']['full_exposure']
        for s in ['XS','S','M','L']:check(alloc[i,a,s]['partial_exposure']==u and alloc[i,a,s]['full_exposure']==v,f'exposure repeated {i,a,s}')
        if u:check(all(alloc[i,a,s]['available_inventory']>=1 for s in ['S','M','L']),f'partial eligibility {i,a}')
        if v:check(all(alloc[i,a,s]['available_inventory']>=3 for s in ['S','M','L']),f'full eligibility {i,a}')
        exp_count[(int(u),int(v))]+=1
for (a,s),(H,R) in warehouse.items():
    used=sum(alloc[i,a,s]['shipped_units'] for i in stores)
    check(abs(used+retained[a,s]-H)<1e-7,f'warehouse balance {(a,s)}: {used}+{retained[a,s]}!={H}')
    check(abs(R-.35*prices[a])<1e-6,f'retention price mismatch {(a,s)}')
revenue=sum(prices[a]*r['expected_sales'] for (i,a,s),r in alloc.items())
rv=sum(R*retained[a,s] for (a,s),(H,R) in warehouse.items())
shipped=sum(r['shipped_units'] for r in alloc.values())
sales=sum(r['expected_sales'] for r in alloc.values())
article={}
for a in prices:
    article[a]={'available':sum(warehouse[a,s][0] for s in ['XS','S','M','L']),'shipped':sum(alloc[i,a,s]['shipped_units'] for i in stores for s in ['XS','S','M','L']),'retained':sum(retained[a,s] for s in ['XS','S','M','L'])}
check(abs(revenue-43996)<.011,'revenue mismatch report')
check(abs(rv-1661.45)<.011,'retained mismatch report')
check(abs(revenue+rv-45657.45)<.011,'objective mismatch report')
check(abs(shipped-392)<1e-6,'shipped mismatch report')
check(abs(sales-566.2)<.011,'sales units mismatch report')
check(len(alloc)==200,'incorrect allocation row count')
check(len(segs)==200,'incorrect segments combos')
check(sum(map(len,segs.values()))==800,'incorrect total segment records')
zeros=sum(1 for x in alloc.values() if x['available_inventory'] == 0 and x['expected_sales']==0)
demand_binding=sum(1 for (i,a,s),x in alloc.items() if abs(x['expected_sales']-stock[i,a,s][1])<1e-5)
seg_binding=sum(1 for k,x in alloc.items() if abs(x['expected_sales'] - min(alpha*x['available_inventory']+beta for _,alpha,beta in segs[k])) < 1e-5)
first_segment=sum(1 for k,x in alloc.items() if abs(x['expected_sales']-(segs[k][0][1]*x['available_inventory']+segs[k][0][2]))<1e-5)
# Compare saved main allocation to ablation exported shipment policies.
abrows=rows('zara_ablation_shipments.csv')
base_mismatch=[]; rerun_mismatch=[]
for r in abrows:
 k=(r['store'],r['article'],r['size'])
 if k not in alloc: errors.append(f'ablation shipment unknown key {k}');continue
 if abs(float(r['best_feasible_baseline'])-alloc[k]['shipped_units'])>1e-6:base_mismatch.append(k)
 if abs(float(r['full_rerun'])-alloc[k]['shipped_units'])>1e-6:rerun_mismatch.append(k)
comparison=rows('zara_ablation_comparison.csv')
print('ASSIGNED prices:',prices)
print('Record counts: allocations',len(alloc),'warehouse',len(warehouse),'segments',sum(map(len,segs.values())),'ablation',len(abrows))
print('Totals: revenue',round(revenue,2),'retention',round(rv,2),'objective',round(revenue+rv,2),'shipped',shipped,'sales',round(sales,3),'retained',sum(retained.values()))
print('Counts: exposure',dict(exp_count),'zero stock/sales',zeros,'demand binding',demand_binding,'saturation binding',seg_binding,'first segment binding',first_segment)
print('Article breakdown:',json.dumps(article,indent=2))
print('Ablation mismatch: saved baseline',len(base_mismatch),'new full rerun',len(rerun_mismatch))
print('CHECK ERRORS:',len(errors),errors[:15])
# independent evaluation all ablation policies
for col in ['best_feasible_baseline','full_rerun','no_exposure','linear_sales']:
    aa={(r['store'],r['article'],r['size']):int(r[col]) for r in abrows}
    rv2=0; err2=[]; rev2=0;sales2=0; full2=part2=none2=0
    for (a,s),(H,R) in warehouse.items():
        used=sum(aa[i,a,s] for i in stores)
        if used>H:err2.append((a,s,used,H))
        rv2+=R*(H-used)
    for i in stores:
        used=sum(aa[i,a,s] for a in prices for s in ['XS','S','M','L'])
        if used>stores[i]:err2.append((i,used,stores[i]))
        for a in prices:
            vals={s:stock[i,a,s][0]+aa[i,a,s] for s in ['XS','S','M','L']}
            e=1 if min(vals[s] for s in ['S','M','L'])>=3 else .6 if min(vals[s] for s in ['S','M','L'])>=1 else 0
            if e==1: full2+=1
            elif e==.6:part2+=1
            else:none2+=1
            for s,q in vals.items():
                b,d=stock[i,a,s]
                f=min(alpha*q+beta for _,alpha,beta in segs[i,a,s])
                z=min(q,d,e*f)
                rev2+=prices[a]*z;sales2+=z
    print(f'{col}: value={rev2+rv2:.2f}, revenue={rev2:.2f}, retained={rv2:.2f}, sales={sales2:.2f}, exp={(full2,part2,none2)}, errors={err2[:2]}')

def eval_ships(sh):
    val=ret=units=0.0;full=partial=0
    for a,s in warehouse:
      H,R=warehouse[a,s];ret+=R*(H-sum(sh[i,a,s] for i in stores))
    for i in stores:
      for a in prices:
        q={s:stock[i,a,s][0]+sh[i,a,s] for s in ['XS','S','M','L']}
        e=(1.0 if min(q[s] for s in ['S','M','L'])>=3 else 0.6 if min(q[s] for s in ['S','M','L'])>=1 else 0)
        full+=e==1;partial+=e==0.6
        for s in ['XS','S','M','L']:
          cap=min(alpha*q[s]+beta for _,alpha,beta in segs[i,a,s])
          z=min(q[s],stock[i,a,s][1],e*cap)
          val+=prices[a]*z;units+=z
    return val+ret,val,ret,units,full,partial

def fcfs():
    left={k:v[0] for k,v in warehouse.items()}; capa=dict(stores);allocation={}
    for i in stores:
      for a in prices:
        for s in ['XS','S','M','L']:
          unmet=max(0,stock[i,a,s][1]-stock[i,a,s][0]);amount=min(unmet,left[a,s],capa[i]);allocation[i,a,s]=int(amount);left[a,s]-=amount;capa[i]-=amount
    return allocation

def proportional():
    sizes=['XS','S','M','L'];allocation={(i,a,s):0 for i in stores for a in prices for s in sizes}
    capa=dict(stores);unmet={k:max(0,d-b) for k,(b,d) in stock.items()}
    st=list(stores)
    for a in prices:
      for s in sizes:
        remaining=warehouse[a,s][0]
        while remaining:
          candidates=[i for i in stores if capa[i]>0 and allocation[i,a,s] < unmet[i,a,s]]
          if not candidates:break
          chosen=min(candidates,key=lambda i:(allocation[i,a,s]/unmet[i,a,s],-unmet[i,a,s],st.index(i)))
          allocation[chosen,a,s]+=1;capa[chosen]-=1;remaining-=1
    return allocation
for name,fn in [('request',fcfs),('proportional',proportional)]:
    sh=fn();v,rev,ret,sales,full,partial=eval_ships(sh)
    print(f'Independent {name} rule: objective={v:.2f} sales EUR={rev:.2f} retained EUR={ret:.2f} sales units={sales:.2f} full={full} partial={partial} shipped={sum(sh.values())}')
