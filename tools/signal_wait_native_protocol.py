"""Bind actual guest returns/handlers to owned native synchronous wait records."""
from signal_wait_guest_protocol import require,only,key,signals
from native_signal_delivery_x86_64_evidence import IMAGE

def mask_words(bits,sigs):
 value=sum(1<<(number-1) for bit,number in enumerate(sigs) if bits&(1<<bit))
 return value&((1<<64)-1),value>>64

def validate_owned_waits(raw,arch,guest,events):
 begins=[r for r in guest if r['tag']=='CASE_BEGIN'];parents=[r for r in guest if r['tag']=='PARENT_PASS'];assigned=set();totals=dict(arms=0,rearms=0,completions=0,commits=0,retirements=0,libc_retries=0,owned_ignored_drains=0,exec_images=0)
 images=[i for i,line in enumerate(raw.splitlines()) if IMAGE.fullmatch(line)]
 for begin,parent in zip(begins,parents):
  part=[r for r in guest if begin['position']<r['position']<parent['position']];native=[r for r in events if begin['position']<r['position']<parent['position']]
  f,a,_,_,_,c=key(begin);child=only([r for r in part if r['tag']=='CHILD'],'native case child');pid=child['pid'];sigs=signals(arch,child['rtmin']);calls=[r for r in part if r['tag']=='BEGIN'];returns=[r for r in part if r['tag']=='RETURN'];handles=[r for r in part if r['tag']=='HANDLE'];owned={}
  assigned.update(r['position'] for r in native);require(all(r['pid']==pid for r in native),'foreign native process in case')
  expected_image=(f and c in (13,14)) or (not f and c==28);case_images=[i for i in images if begin['position']<i<parent['position']]
  require(len(case_images)==int(expected_image),'exec image count within case')
  if case_images:
   commit=only([r for r in part if r['tag']=='EVENT' and r['tag_value']=='EXEC_COMMIT'],'native exec commit');fresh=only([r for r in part if r['tag']=='REPLACED'],'fresh image marker');require(commit['position']<case_images[0]<fresh['position'],'exec image publication ordering');totals['exec_images']+=1
  native_assigned=set()
  for call in calls:
   who,ordinal=call['actor'],call['ordinal'];ret=[r for r in returns if (r['actor'],r['ordinal'])==(who,ordinal)];later=[r['position'] for r in calls if r['actor']==who and r['position']>call['position']]
   high=ret[0]['position'] if ret else min(later,default=parent['position']);rows=[r for r in native if r['tid']==call['tid'] and call['position']<r['position']<high];arms=[r for r in rows if r['event']=='ARM'];terms=[r for r in rows if r['event']=='COMPLETE'];commits=[r for r in rows if r['event']=='COMMIT'];retires=[r for r in rows if r['event']=='RETIRE']
   native_assigned.update(r['position'] for r in rows)
   deferred=(f and c>=2 and not(c==4 and ordinal==1)) or (not f and c>=13 and c not in (21,22,23))
   expected_arms=2 if deferred and not f and a and c in (17,18) else int(deferred)
   require(len(arms)==expected_arms,'exact per-invocation native admissions')
   if not deferred:require(not rows,'native wait for immediate/admission path');continue
   totals['arms']+=len(arms);totals['rearms']+=sum(r['event']=='REARM' for r in rows);totals['completions']+=len(terms);totals['commits']+=len(commits);totals['retirements']+=len(retires);totals['libc_retries']+=expected_arms-1
   for arm in arms:
    require((arm['pid'],arm['tid'],arm['kind'],arm['syscall'],arm['set'],arm['info'],arm['sigsetsize'])==(pid,call['tid'],'suspend' if f else 'timed',call['syscall'],call['set'],call['info'],call['size']),'native copied call identity')
    require((arm['wanted0'],arm['wanted1'])==mask_words(call['wanted'],sigs) and (arm['original0'],arm['original1'])==mask_words(call['mask'],sigs),'native copied and original masks')
    if not a:require(arm['pc']==call['resume'] and arm['timeout']==call['timeout'],'raw continuation/input pointers')
    else:require(bool(arm['timeout'])==bool(call['timeout']),'libc finite timeout ownership')
    owned[arm['position']]=call
   is_retired=(f and c in (14,15)) or (not f and c in (28,29));is_handler=f and not is_retired
   if is_retired:
    require(len(retires)==1 and not terms and not commits and not ret,'cancelled/exec wait terminal')
    terminal=retires[0];require(terminal['cause']==('group' if c in (15,29) else 'exec'),'retirement reason')
    trigger=only([r for r in part if r['tag']=='SEND' and r['signal']==9] if c in (15,29) else [r for r in part if r['tag']=='EVENT' and r['tag_value']=='EXEC_COMMIT'],'retirement trigger')
    require(arms[0]['position']<trigger['position']<terminal['position']<(case_images[0] if case_images else parent['position']),'retirement trigger/image boundary')
   elif is_handler:
    require(not retires and len(commits)==1 and bool(terms),'suspend frame publication')
    require(all((r['outcome'],r['result'],r['published'],r['staged'])==('eintr',-4,0,1) for r in terms),'suspend staged result')
    matching=[r for r in handles if r['actor']==who and call['position']<r['position']<high];h=only(matching,'committed handler execution');commit=commits[0]
    require(commit['signal']==h['signal'] and commit['position']<h['position'] and terms[-1]['position']<commit['position'],'handler frame commit before execution')
    require(terms[-1]['signal']==h['signal'] and terms[-1]['sender_pid']==pid and terms[-1]['sender_uid']==child['uid'] and terms[-1]['code']==h['code'],'caught selection source')
    if ret:
     returned=only([r for r in part if r['tag']=='EVENT' and r['tag_value']=='HANDLER_RETURN' and r['actor']==who and h['position']<r['position']<ret[0]['position']],'handler return before suspended continuation');require(returned['value']==h['signal'],'returning handler number')
   else:
    require(len(terms)==len(arms) and not retires and not commits and len(ret)==1,'timed exact terminal/return')
    for index,(arm,term) in enumerate(zip(arms,terms)):
     require(term['origin_position']==arm['position'] and arm['position']<term['position'],'terminal origin binding')
     if index+1<len(arms):require(term['outcome']=='eintr' and term['result']==-4 and term['position']<arms[index+1]['position'],'libc EINTR retry admission')
    result=ret[0]['value'];result=-ret[0]['errno'] if a and result==-1 else result;last=terms[-1]
    require(last['result']==result and last['outcome']==('received' if result>0 else 'timeout' if result==-11 else 'eintr'),'native completion matches user result')
    if result>0:
     info=only([r for r in part if r['tag']=='INFO' and (r['actor'],r['ordinal'])==(who,ordinal)],'native received siginfo')
     require((last['signal'],last['code'],last['sender_pid'],last['sender_uid'])==(info['signal'],info['code'],info['sender'],info['uid']),'native signal source equals copied bytes')
    if c in (17,18):
     interrupted=terms[0];require((interrupted['outcome'],interrupted['signal'],interrupted['code'],interrupted['sender_pid'],interrupted['sender_uid'])==('eintr',sigs[1] if c==17 else sigs[4],-6 if c==17 else 0,pid,child['uid']),'outside-wanted interrupt source')
     if c==17:
      h=only([r for r in handles if r['actor']==who and call['position']<r['position']<high],'timed interruption handler');require(interrupted['position']<h['position']<(arms[1]['position'] if a else ret[0]['position']),'timed mask restoration before handler/retry')
   # Every consuming/interrupt completion follows a published matching send.
   for term in terms:
    if term['outcome'] in ('received','eintr','efault'):
     sends=[r for r in part if r['tag']=='SEND' and r['signal']==term['signal'] and r['pid']==term['sender_pid'] and r['uid']==term['sender_uid'] and r['position']<term['position']]
     require(bool(sends),'native delivery before matching generated signal')
  require(native_assigned=={r['position'] for r in native},'unassigned native record')
  # A guest AWAIT is accepted only while an actual registration owns that TID.
  for awaited in [r for r in part if r['tag']=='AWAIT']:
   prior=[r for r in native if r['tid']==awaited['tid'] and r['position']<awaited['position']]
   require(bool(prior) and prior[-1]['event'] in ('ARM','REARM'),'await lacks active native registration')
   call=owned[prior[-1]['origin_position']];require(call['actor']==awaited['target'],'await caller identity')
  if not f and c in (19,20) or f and c==11:
   mutation=only([r for r in part if r['tag']=='EVENT' and r['tag_value'] in ('MUTATE_SET','MUTATE_TIMEOUT')],'input mutation');prior=[r for r in native if r['position']<mutation['position']];require(prior and prior[-1]['event'] in ('ARM','REARM'),'mutation before copied request ownership')
  if f and c==9:
   drains=[r for r in part if r['tag']=='EVENT' and r['tag_value']=='IGNORED_DRAIN_OWNED']
   for drain in drains:
    prior=[r for r in native if r['position']<drain['position']];require(prior and prior[-1]['event'] in ('ARM','REARM'),'ignored drain ended suspend ownership')
    pending=[r for r in part if r['tag']=='PENDING' and r['actor']==9 and prior[-1]['position']<r['position']<drain['position']];require(pending and pending[-1]['bits']==0,'ignored pending not drained while suspend remains owned');totals['owned_ignored_drains']+=1
 require(assigned=={r['position'] for r in events},'native wait outside dedicated cases');return totals
