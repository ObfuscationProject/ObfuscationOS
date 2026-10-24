"""Full blocking-write record grammar and committed-prefix invariants."""
def schemas(re,N,V):
 result=[]
 for vector in (False,True):
  prefix=b'OK_NATIVE_PIPE_'+(b'WRITEV_LARGE_' if vector else b'WRITE_LARGE_');field=b'array' if vector else b'input';tail=(V if vector else b'')+rb' committed='+N
  identity=rb'pid='+N+rb' tid='+N+rb' wait='+N+rb' request='+N+b' '+field+b'='+N+rb' fd='+N+rb' description='+N+rb' pipe='+N+rb' bytes='+N+tail
  pub=rb'pid='+N+rb' tid='+N+rb' request='+N+rb' wait='+N+rb' origin='+N
  args=rb' pc='+N+rb' syscall='+N+rb' fd='+N+b' '+field+b'='+N+rb' bytes='+N+tail
  for tag,expression in [('WAIT',prefix+b'WAIT '+identity+rb' stage=(arm|rearm) live='+N),('COMPLETE',prefix+b'COMPLETE '+identity+rb' result=(-?[0-9]+) outcome=(ready|efault|cancelled|error|interrupted) pinned=([01]) live='+N),('ORIGIN',prefix+b'ORIGIN '+pub+args),('SIGNAL',prefix+b'SIGNAL '+pub+rb' signal='+N+rb' outcome=(eintr|restart|partial)'+args+rb' pinned=([01]) live='+N)]:result.append((re.compile(expression),1,vector,tag,field.decode(),True))
 return result

def terminal(row,prior):
 committed=row['committed'];value=row['result'];cause=row['outcome'];delta=committed-prior
 if not 0<=delta<=4096 or cause in ('efault','cancelled','interrupted') and delta:raise ValueError('large pipe terminal changed unpublished cursor')
 if cause=='ready':valid=delta>0 and value==committed and 0<value<=row['bytes']
 elif cause=='efault':valid=value==(committed or -14)
 elif cause=='error':valid=value==committed if committed else value<0 and value not in (-4,-14,-125)
 elif cause=='cancelled':valid=value==-125 or committed>0 and value==committed
 elif cause=='interrupted':valid=value==committed if committed else value in (-4,0)
 else:valid=False
 if not valid:raise ValueError('large pipe terminal result/cause/prefix mismatch')
