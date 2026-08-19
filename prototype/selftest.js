const wait=(ms=60)=>new Promise(r=>setTimeout(r,ms));
// wait for the scan to actually have layout, rather than guessing a delay:
// served mode renders pages on demand, so the image can arrive late
async function ready(ms=8000){
  const t0=Date.now();
  while(Date.now()-t0<ms){
    const im=document.querySelector("#scan");
    if(im && im.naturalWidth>0 && im.clientHeight>0 && document.querySelectorAll("#rows tr").length) return true;
    await wait(100);
  }
  return false;
}
function rows_len(){ try{ return document.querySelectorAll("#rows tr").length; }catch(e){ return -1; } }
window.addEventListener("load",async()=>{
 const out=[]; const ok=(n,c)=>out.push((c?"PASS":"FAIL")+" "+n);
 const q=s=>document.querySelector(s);
 try{
  // The corpus used to hold one transcribed document, so whatever opened first
  // was the sample. Now the folder indexer transcribes everything, so the
  // sample has to be asked for by name before the assertions about its content.
  for(let i=0;i<60;i++){                     // the corpus arrives after load
    if(typeof DB!=="undefined" && DB && DB.documents) break;
    await wait(100);
  }
  if(typeof DB!=="undefined" && DB && DB.documents){
    const i=DB.documents.findIndex(d=>(d.file||"").includes("017397") && d.rows);
    if(i>=0 && typeof openDoc==="function"){ openDoc(i); await wait(600); }
  }
  ok("page and rows ready", await ready());
  ok("rows rendered=26", document.querySelectorAll("#rows tr").length===26);
  ok("scan image loaded", q("#scan").naturalWidth>0);
  ok("band painted", !q("#bandBox").hidden && parseFloat(q("#bandBox").style.height)>0);
  ok("scope defaults to name", q("#scope").value==="name");

  q("#findq").value="paul"; q("#findq").dispatchEvent(new Event("input")); await wait();
  const paulHits=[...document.querySelectorAll("#rows tr.hit")];
  ok("name scope: paul -> 1 row (no Sao Paulo)", paulHits.length===1);
  q("#scope").value="all"; q("#scope").dispatchEvent(new Event("change")); await wait();
  ok("all scope: paul -> more rows", document.querySelectorAll("#rows tr.hit").length>1);
  q("#scope").value="name"; q("#scope").dispatchEvent(new Event("change")); await wait();

  q("#findq").value="vasquez"; q("#findq").dispatchEvent(new Event("input")); await wait();
  ok("fuzzy: vasquez finds VAZQUEZ too", document.querySelectorAll("#rows tr.hit").length===2);
  q("#findq").value="joao"; q("#findq").dispatchEvent(new Event("input")); await wait();
  ok("variant: joao finds SCHRADER", [...document.querySelectorAll("#rows tr.hit")].some(t=>t.textContent.includes("SCHRADER")));
  q("#scope").value="occupation"; q("#scope").dispatchEvent(new Event("change"));
  q("#findq").value="jornaleiro"; q("#findq").dispatchEvent(new Event("input")); await wait();
  ok("column scope: occupation -> 3 rows", document.querySelectorAll("#rows tr.hit").length===3);
  q("#scope").value="name"; q("#findq").value=""; q("#findq").dispatchEvent(new Event("input")); await wait();

  const before=q("#bandBox").style.top;
  document.querySelector('#rows tr[data-i="12"]').click(); await wait();
  ok("selecting row moves band", q("#bandBox").style.top!==before);
  ok("selected row marked", document.querySelectorAll("#rows tr.sel").length===1);

  const sp=q("#scanPane"), rp=q("#rowPane");
  ok("scan pane scrollable", sp.scrollHeight>sp.clientHeight+10);
  const s0=sp.scrollTop;
  const rpMax=rp.scrollHeight-rp.clientHeight, spMax=sp.scrollHeight-sp.clientHeight;
  rp.scrollTop=Math.max(1,rpMax*0.75); rp.dispatchEvent(new Event("scroll")); await wait();
  ok(`rows scroll drives scan pane [rpMax=${Math.round(rpMax)} spMax=${Math.round(spMax)} s0=${Math.round(s0)} s1=${Math.round(sp.scrollTop)} imgH=${Math.round(q("#scan").clientHeight)} rows=${rows_len()}]`, sp.scrollTop!==s0);
  q("#lock").click(); await wait();
  const s1=sp.scrollTop; rp.scrollTop=0; rp.dispatchEvent(new Event("scroll")); await wait();
  ok("unlock stops sync", sp.scrollTop===s1);
  q("#lock").click(); await wait();
  const r0=rp.scrollTop;
  sp.scrollTop=Math.max(1,(sp.scrollHeight-sp.clientHeight)*0.9); sp.dispatchEvent(new Event("scroll")); await wait();
  ok(`scan scroll drives rows pane [r0=${Math.round(r0)} r1=${Math.round(rp.scrollTop)}]`, rp.scrollTop!==r0);

  q("#crop").click(); await wait();
  ok("name column box shown", !q("#nameBox").hidden && parseFloat(q("#nameBox").style.width)>0);
  document.querySelector('#rows tr[data-i="0"] td[data-v]').click(); await wait();
  ok("verify marks row", document.querySelector('#rows tr[data-i="0"]').classList.contains("verified"));
  ok("unreadable shown as ilegivel", document.querySelectorAll("#rows .null").length>0);
  ok("ditto marked", document.querySelectorAll("#rows .ditto").length>0);

  // confidence must read as confidence, not as a spellchecker complaint
  const dots=document.querySelectorAll("#rows .dot");
  ok("confidence shown as semaphore dots", dots.length>0);
  ok("no wavy underline left behind",
     !document.querySelector("#rows .lo[style*='wavy'], #rows .mid[style*='wavy']"));
  ok("dots carry a text label for screen readers and colour-blind readers",
     [...dots].every(d=>(d.getAttribute("aria-label")||"").length>3));
  ok("all three semaphore states present on this page",
     ["hi","mid","lo"].every(k=>document.querySelector(".dot."+k)));
  // manual transcription must survive a refresh, or an hour of typing is lost
  if(typeof SERVED!=="undefined" && SERVED){
    const cell0=document.querySelector('#rows tr[data-i="0"] [data-f="occupation"]');
    if(cell0){
      cell0.textContent="SIRVIENTA"; cell0.dispatchEvent(new Event("input",{bubbles:true}));
      await wait(120);
      ok("edit marks unsaved state", /não salvas/.test(document.getElementById("stat").textContent));
      let saved=false;
      for(let i=0;i<25 && !saved;i++){ await wait(200);
        saved=/salvo/.test(document.getElementById("stat").textContent); }
      ok("edit is autosaved to the server", saved);
    }
  }

  const hiBefore=document.querySelectorAll(".dot.hi").length;
  const ed=document.querySelector('#rows tr[data-i="4"] [data-f="nationality"]');
  if(ed){ ed.textContent="BELGA"; ed.dispatchEvent(new Event("input",{bubbles:true})); await wait();
    ok("editing a cell clears its stale confidence",
       document.querySelectorAll(".dot.hi").length>hiBefore); }

  // Structure without a model: on a ruled page the grid is measurable, so an
  // untranscribed document can still produce an empty table to fill in by hand.
  if(typeof SERVED!=="undefined" && SERVED){
    const untranscribed=[...document.querySelectorAll(".doc")]
      .find(d=>!d.querySelector(".badge"));
    if(untranscribed){
      untranscribed.click(); await wait(700);
      const btn=document.getElementById("dogrid");
      ok("empty-grid button offered when untranscribed", !!btn);
      if(btn){
        btn.click();
        let built=false;
        for(let i=0;i<40 && !built;i++){
          await wait(250);
          built = document.querySelectorAll("#rows tr").length>0
                  || /Não foi possível detectar/.test(document.getElementById("empty").textContent);
        }
        const madeRows=document.querySelectorAll("#rows tr").length;
        const declined=/Não foi possível detectar/.test(document.getElementById("empty").textContent);
        ok(`grid either builds rows or says it cannot [rows=${madeRows} declined=${declined}]`,
           madeRows>0 || declined);
        if(madeRows>0){
          ok("generated cells are empty, not invented",
             [...document.querySelectorAll('#rows [data-f="nationality"]')]
               .every(td=>/^\s*(ilegível)?\s*$/.test(td.textContent)));
        }
      }
    }
  }

  // search across the index: the control exists and answers, even when empty
  const cq=document.getElementById("corpusq");
  ok("corpus search box present", !!cq);
  if(cq){
    cq.value="amparo"; cq.dispatchEvent(new Event("input",{bubbles:true}));
    let answered=false;
    for(let i=0;i<24 && !answered;i++){
      await wait(200);
      answered = document.querySelectorAll("#corpushits .hit").length>0
              || !!document.querySelector("#corpushits .none");
    }
    ok("corpus search answers, with hits or with a plain 'nothing' line", answered);
    ok("search says how much was searched",
       /linhas indexadas/.test(document.getElementById("corpushits").textContent));
    const hit=document.querySelector("#corpushits .hit");
    if(hit){
      const want=+hit.dataset.row;
      hit.click();
      // the document's page image is fetched on demand, so wait for the state
      // rather than for a guessed delay
      let selRow=null;
      for(let i=0;i<40;i++){
        await wait(150);
        selRow=document.querySelector("#rows tr.sel");
        if(selRow && (!want || selRow.querySelector(".num").textContent.trim()===String(want))) break;
      }
      ok("clicking a hit opens its document and selects that row",
         !!selRow && (!want || selRow.querySelector(".num").textContent.trim()===String(want)));
      let banded=false;
      for(let i=0;i<40 && !banded;i++){
        await wait(150);
        banded=!document.getElementById("bandBox").hidden;
      }
      ok("the scan band follows the hit", banded);
    }
    cq.value=""; cq.dispatchEvent(new Event("input",{bubbles:true}));
  }

  // folder indexing: the main action must be visible and must explain itself
  if(location.pathname==="/selftest" || document.querySelector("#indexbar")){
    const bar=document.getElementById("indexbar");
    ok("index bar present", !!bar);
    if(bar){
      for(let i=0;i<20 && !bar.textContent.trim();i++) await wait(150);
      ok("index bar says something", bar.textContent.trim().length>0);
      const btn=document.getElementById("doindex");
      ok("index button offered", !!btn);
      if(btn && btn.disabled){
        ok("disabled index button explains why",
           /model|motor|indispon/i.test(bar.textContent));
      }
    }
  }

  // Indexing takes the machine, so listing a folder can take half a minute and
  // the page looks broken with nothing on it to say why. The bar has to be
  // asked for on its own, before the folder, or the one thing able to explain
  // the wait is the one thing that cannot appear until it is over.
  {
    const src = document.documentElement.innerHTML;
    ok("index bar is booted before the folder listing",
       /bootIndexBar\(\);/.test(src));
    ok("index bar is booted before the folder is asked for",
       src.indexOf("bootIndexBar();") < src.lastIndexOf("loadData()"));
    ok("a running index warns that the app will be slow",
       /ocupa a m|fica lento/i.test(src));
    ok("a finished index says to reload",
       /Recarregue a p|reloadpage/i.test(src));
  }

  // The engine and the grid endpoint named the same measurement differently,
  // and nothing here noticed because these assertions run against the
  // hand-fitted sample, which has always carried `row_bands`. So the engine's
  // shape is fed in explicitly: without it, both sides pass while disagreeing,
  // and clicking a name silently stops highlighting it on every page that was
  // actually read.
  {
    const src = document.documentElement.innerHTML;
    ok("band() reads the engine's key as well as the grid's",
       /row_bands\s*\|\|\s*g\.rows/.test(src));
    ok("an unmeasured band hides the box instead of painting NaN",
       /isFinite\(bnd\[0\]\)/.test(src));
    ok("the name column is derived when only columns were stored",
       /function nameColumn\(\)/.test(src));

    if(typeof band === "function" && typeof D !== "undefined"){
      const keep = D;
      try{
        D = {geometry:{rows:[[0.1,0.2],[0.2,0.3]], columns:[0.08,0.35,0.5]}};
        const b0 = band(0);
        ok("engine-shaped geometry yields a real band",
           !!b0 && isFinite(b0[0]) && isFinite(b0[1]) && b0[0]===0.1);
        const nc = nameColumn();
        ok("engine-shaped geometry yields a name column",
           !!nc && nc[0]===0.08 && nc[1]===0.35);
        D = {geometry:{}};
        ok("geometry with nothing measured yields no band", band(0)===null);
      } finally { D = keep; }
    }
  }

 }catch(err){ out.push("THREW "+(err&&err.message)); }
 document.getElementById("warn").textContent="RESULTS>> "+out.join(" | ");
});
