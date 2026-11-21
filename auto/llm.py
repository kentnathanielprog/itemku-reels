"""Thin Claude API wrapper for the daily producer (one call per ROLE for the whole batch, not per story).
- needs ANTHROPIC_API_KEY (env var) unless LLM_MOCK_DIR is set (offline test with canned answers)
- structured output (JSON schema), prompt-cached system prompt, refusal/max_tokens handling, usage + cost log (state/llm_usage.jsonl)"""
import os,json,time,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent; LOG=ROOT/'state'/'llm_usage.jsonl'
PRICE={'claude-opus-5-5':(4.0,20.0),'claude-sonnet-5-5':(2.0,10.0),'claude-haiku-5-5':(0.10,0.50),'claude-fable-5-2':(8.0,40.0)}   # $/MTok in,out (cache read 0.1x, write 1.25x)
FALLBACK_MODELS={'claude-opus-5-5','claude-sonnet-5-5','claude-fable-5-2'}
class LLMError(Exception): pass
def _cfg_backend():
    try: return json.loads((ROOT/'config.json').read_text()).get('llm',{}).get('backend','api')
    except Exception: return 'api'
_mock_n={}
def cost(model,i,o,cr=0,cw=0):
    pi,po=PRICE.get(model,(4.0,20.0)); return (i*pi+o*po+cr*pi*0.1+cw*pi*1.25)/1e6
def _log(rec): 
    LOG.parent.mkdir(exist_ok=True); open(LOG,'a').write(json.dumps(rec,ensure_ascii=False)+'\n')
def _validate(data,schema):
    """minimal check (required keys + top-level types) so a bad CLI answer triggers a retry"""
    if schema.get('type')=='object':
        if not isinstance(data,dict): return 'bukan objek'
        miss=[k for k in schema.get('required',[]) if k not in data]
        if miss: return f'kunci hilang: {miss}'
    return None
def _cli_call(role,system,user,schema,model,effort):
    """Backend 'claude_cli': pakai langganan Claude lewat `claude -p` (token OAuth CLAUDE_CODE_OAUTH_TOKEN). Tanpa saldo API.
    Dijalankan di folder sementara bersih supaya CLAUDE.md repo tidak ikut termuat; semua tool mati kecuali Read (hanya untuk gambar vision)."""
    import subprocess,tempfile,base64,shutil
    tmp=tempfile.mkdtemp(prefix='llmcli_')
    try:
        if isinstance(user,list):
            parts=[]; n=0
            for b in user:
                if b.get('type')=='image':
                    n+=1; f=pathlib.Path(tmp)/f'img{n}.jpg'; f.write_bytes(base64.b64decode(b['source']['data'])); parts.append(f'[gambar #{n}: {f}]')
                else: parts.append(b.get('text',''))
            user='\n'.join(parts)+('\n\nLihat setiap gambar di atas dengan tool Read sebelum menjawab.' if n else '')
        else: n=0
        cmd=['claude','-p',user,'--output-format','json','--json-schema',json.dumps(schema),'--model',model,'--append-system-prompt',system,
             '--no-session-persistence','--disable-slash-commands','--setting-sources','','--effort',effort]
        cmd+=['--tools','Read','--allowedTools','Read','--add-dir',tmp] if n else ['--tools','']
        last=None
        for attempt in (1,2):
            try: pr=subprocess.run(cmd,cwd=tmp,capture_output=True,text=True,timeout=int(os.environ.get('LLM_CLI_TIMEOUT','900')))
            except subprocess.TimeoutExpired: last='timeout'; continue
            try: j=json.loads(pr.stdout)
            except Exception: last=f'keluaran CLI bukan JSON (kode {pr.returncode}): {(pr.stderr or pr.stdout)[:200]}'; continue
            if j.get('is_error'): last=f"CLI error: {str(j.get('result'))[:200]}"; 
            else:
                data=j.get('structured_output')
                if data is None:
                    try: data=json.loads(j.get('result') or '')
                    except Exception: last='jawaban bukan JSON'; data=None
                if data is not None:
                    bad=_validate(data,schema)
                    if not bad:
                        us=j.get('usage') or {}; u={'in':us.get('input_tokens',0),'out':us.get('output_tokens',0),'cache_read':us.get('cache_read_input_tokens',0) or 0,'cache_write':us.get('cache_creation_input_tokens',0) or 0}
                        u['usd']=0.0; u['list_usd']=round(j.get('total_cost_usd') or 0,5)   # langganan: tidak ada tagihan; list_usd hanya perkiraan harga API
                        _log({'t':time.time(),'role':role,'model':model,'backend':'claude_cli','turns':j.get('num_turns'),**u}); return data,u
                    last=f'skema tidak cocok: {bad}'
            if attempt==1: print(f'  (CLI ulang: {last})',file=sys.stderr)
        raise LLMError(f'claude CLI gagal: {last}. Cek CLAUDE_CODE_OAUTH_TOKEN dan batas langganan.')
    finally: shutil.rmtree(tmp,ignore_errors=True)
def call_json(role,system,user,schema,model,effort='medium',max_tokens=8000,fallbacks=True):
    """returns (data, usage_dict). One request; JSON guaranteed by output_config.format (API) or --json-schema (claude_cli)."""
    md=os.environ.get('LLM_MOCK_DIR')
    if md:
        n=_mock_n[role]=_mock_n.get(role,0)+1; f=pathlib.Path(md)/f'{role}_{n}.json'
        if not f.exists(): raise LLMError(f'mock tidak ada: {f}')
        u={'in':0,'out':0,'cache_read':0,'cache_write':0,'usd':0.0}; _log({'t':time.time(),'role':role,'model':'MOCK',**u}); return json.loads(f.read_text()),u
    if os.environ.get('LLM_BACKEND','').lower()=='claude_cli' or (not os.environ.get('LLM_BACKEND') and _cfg_backend()=='claude_cli'):
        if not os.environ.get('CLAUDE_CODE_OAUTH_TOKEN') and not os.environ.get('ANTHROPIC_API_KEY') and not os.environ.get('LLM_CLI_ALLOW_LOCAL_LOGIN'):
            raise LLMError('CLAUDE_CODE_OAUTH_TOKEN belum diisi (buat dengan `claude setup-token`, simpan sebagai secret). Jangan tempel di chat.')
        return _cli_call(role,system,user,schema,model,effort)
    if not os.environ.get('ANTHROPIC_API_KEY') and not os.environ.get('ANTHROPIC_AUTH_TOKEN'):
        raise LLMError('ANTHROPIC_API_KEY belum diisi (variabel lingkungan). Isi sendiri di pengaturan lingkungan; jangan tempel di chat.')
    import anthropic
    client=anthropic.Anthropic(max_retries=3)
    kw=dict(model=model,max_tokens=max_tokens,system=[{"type":"text","text":system,"cache_control":{"type":"ephemeral"}}],
            messages=[{"role":"user","content":user}],output_config={"effort":effort,"format":{"type":"json_schema","schema":schema}})
    resp=None
    if fallbacks and model in FALLBACK_MODELS:      # server-side refusal fallback (beta); if the API rejects the combo, retry plain
        try: resp=client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],fallbacks="default",**kw)
        except (anthropic.BadRequestError,TypeError) as e: print(f'  (fallbacks ditolak, ulang tanpa: {str(e)[:80]})',file=sys.stderr)
    try:
        if resp is None: resp=client.messages.create(**kw)
    except anthropic.AuthenticationError: raise LLMError('API key ditolak (AuthenticationError)')
    except anthropic.RateLimitError as e: raise LLMError(f'rate limit: coba lagi nanti ({e.response.headers.get("retry-after","?")}s)')
    except anthropic.APIConnectionError: raise LLMError('koneksi ke api.anthropic.com gagal (cek daftar domain lingkungan)')
    except anthropic.APIStatusError as e: raise LLMError(f'API error {e.status_code}: {e.message[:200]}')
    if resp.stop_reason=='refusal': raise LLMError(f'ditolak model (refusal): {getattr(resp.stop_details,"category",None)}')
    if resp.stop_reason=='max_tokens': raise LLMError('keluaran terpotong (max_tokens): naikkan max_tokens')
    text=next((b.text for b in resp.content if b.type=='text'),None)
    if text is None: raise LLMError('tidak ada blok teks pada jawaban')
    us=resp.usage; u={'in':us.input_tokens,'out':us.output_tokens,'cache_read':getattr(us,'cache_read_input_tokens',0) or 0,'cache_write':getattr(us,'cache_creation_input_tokens',0) or 0}
    u['usd']=round(cost(model,u['in'],u['out'],u['cache_read'],u['cache_write']),5)
    _log({'t':time.time(),'role':role,'model':model,'request_id':getattr(resp,'_request_id',None),**u})
    return json.loads(text),u
