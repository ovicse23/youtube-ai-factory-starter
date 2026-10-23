'use strict';
const $ = (s) => document.querySelector(s);
const status = (s, error=false) => { $('#toast').textContent = s; $('#toast').style.color = error ? '#ffb8b8' : '#9be6b7'; };
function selected(){ return document.querySelector('input[name="provider"]:checked')?.value || 'auto'; }
function describe(){
 const p=selected(), f=$('#fallback').checked;
 $('#explain').textContent = p==='gemini' ? 'Only Gemini/Antigravity research is permitted. vidIQ will not be called or charged.' : p==='vidiq' ? f ? 'Use vidIQ first, fall back to Gemini if unavailable; clearly mark missing vidIQ metrics.' : 'Only vidIQ; if disconnected or out of credits, research stops.' : f ? 'Auto: prefer vidIQ MCP when connected and credits are sufficient; otherwise Gemini.' : 'Auto: try vidIQ, stop if unavailable because Gemini fallback is disabled.';
 $('#fallback').disabled = p==='gemini';
}
async function init(){
 try {
  const r=await fetch('/api/settings'); if (!r.ok) throw new Error('Could not load settings');
  const s=await r.json();
  document.querySelector(`input[name="provider"][value="${s.research.provider}"]`).checked = true;
  $('#depth').value=s.research.depth;
  $('#fallback').checked=s.research.fallback_to_gemini;
  describe();
 } catch(e){status(e.message,true)}
}
async function save(){
 try {
  const payload={provider:selected(),depth:$('#depth').value,fallback_to_gemini:$('#fallback').checked};
  const r=await fetch('/api/research-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const data=await r.json(); if (!r.ok) throw new Error(data.error || 'Failed to save');
  describe(); status(`Saved! Research mode: ${data.research.provider}. Video production: ${data.video.provider}.`);
 } catch(e){status(e.message,true)}
}
async function preview(){
 try {const r=await fetch('/api/research-plan'); if(!r.ok)throw new Error('Could not create plan');$('#instructions').textContent=await r.text();status('Instructions refreshed from saved settings.');}
 catch(e){status(e.message,true)}
}
document.querySelectorAll('input[name="provider"]').forEach(el=>el.addEventListener('change',describe));
$('#fallback').addEventListener('change',describe);
$('#save').addEventListener('click',save);
$('#preview').addEventListener('click',preview);
$('#copy').addEventListener('click',async()=>{const s=$('#instructions').textContent;if(s.startsWith('Click')){status('Preview instructions before copying.',true);return;}try{await navigator.clipboard.writeText(s);status('Copied research instructions.');}catch(e){status('Clipboard unavailable; select and copy the text manually.',true);}});
init();
