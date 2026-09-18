import json, re, collections
d = json.load(open("/tmp/wp25/wp44-triage/_fl_diffs.json")); res = d["res"]
cl = json.load(open("/tmp/wp25/wp44-triage/_fl_clusters_final.json"))
def content(diff):
    out=[]
    for l in diff:
        if l.startswith("@@"): continue
        t=l[1:].strip()
        if re.match(r'^(async )?def x',t) or t=="=>": continue
        out.append((l[0],t))
    return out
def sig(k):
    cs=content(res[k]["diff"])
    M=" ~ ".join(t for s,t in cs if s=="-"); P=" ~ ".join(t for s,t in cs if s=="+")
    return M,P

# --- split CBINIT ---
cb_key, cb_cfg, cb_name = [], [], []
for k in cl["CBINIT_dict_entry"]:
    M,P = sig(k)
    m0=re.match(r'^"?([A-Za-z_]+)":?\s*$', M.split("CircuitBreaker")[0].strip('" :')) if "CircuitBreaker" in M else None
    # key change: the quoted dict key differs
    kq_m = re.match(r'^"([A-Za-z_]+)":', M); kq_p = re.match(r'^"([A-Za-z_]+)":', P)
    if kq_m and kq_p and kq_m.group(1)!=kq_p.group(1):
        cb_key.append(k)
    elif "config=_cb_config" in M and "config=_cb_config" not in P:
        cb_cfg.append(k)
    elif "self._breakers.get(endpoint" in (M+P):
        cb_key.append(k)  # fallback default in _get_breaker — but that's CBQ... check: these 2 were dictline
    else:
        cb_name.append(k)
print("CBINIT: key", len(cb_key), "cfg", len(cb_cfg), "name", len(cb_name))
for k in cb_key: print("  KEY", k.split("ǁ")[-1], "|", sig(k)[0][:70], "=>", sig(k)[1][:70])
for k in cb_cfg[:3]: print("  CFG", sig(k)[0][:70], "=>", sig(k)[1][:70])

# --- split DUR ---
dur_log, dur_metric = [], []
for k in cl["DUR_duration_math"]:
    M,P = sig(k)
    if "ai_duration" in (M+P) or "ai_start_time" in (M+P):
        dur_metric.append(k)
    else:
        dur_log.append(k)
print("DUR: log-only", len(dur_log), "ai-metric", len(dur_metric))
fn_c = collections.Counter(k.split("ǁ")[-1].rsplit("__mutmut")[0] for k in dur_metric)
print("  ai fn:", dict(fn_c))

# --- split ENC ---
enc_mode, enc_qual = [], []
for k in cl["ENC_encode"]:
    M,P = sig(k)
    if "quality" in (M+P) or "format=" in (M+P):
        enc_qual.append(k)
    else:
        enc_mode.append(k)
print("ENC: mode/decode", len(enc_mode), "format/quality", len(enc_qual))
for k in enc_mode: print("  MODE", k.split("ǁ")[-1], "|", sig(k)[0][:80], "=>", sig(k)[1][:80])
for k in enc_qual: print("  QUAL", k.split("ǁ")[-1], "|", sig(k)[0][:80], "=>", sig(k)[1][:80])

# --- inspect MSG_raise_text & LOG_call ---
print("=== MSG sample")
for k in cl["MSG_raise_text"][:12]:
    M,P=sig(k); print("  ", k.split("ǁ")[-1], "|", M[:90], "=>", P[:60])
print("=== LOG_call: arg-None vs text")
lg_none, lg_txt = [], []
for k in cl["LOG_call"]:
    M,P = sig(k)
    if re.search(r'\((None)?\)?$', P) and "None" in P and not re.search(r"'|\"XX|f?\"", P.replace("None","")) or P.strip().endswith("(None)") or P.strip()=="()":
        lg_none.append(k)
    else:
        lg_txt.append(k)
print("LOG none/removed:", len(lg_none), "text:", len(lg_txt))

json.dump({"cb_key":cb_key,"cb_cfg":cb_cfg,"cb_name":cb_name,"dur_log":dur_log,"dur_metric":dur_metric,"enc_mode":enc_mode,"enc_qual":enc_qual},
          open("/tmp/wp25/wp44-triage/_fl_splits.json","w"), indent=1)
