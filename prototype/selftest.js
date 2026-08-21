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
  // the page knows whether it was served; assertions that need the API ask this
  const SERVED_RUN = typeof SERVED!=="undefined" && SERVED;
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

  // The scope control was invisible on the header and its native popup could
  // only be dismissed by choosing an option.
  q("#scopebtn").click(); await wait(60);
  ok("the scope menu opens on the control", !q("#scopemenu").hidden);
  q("#scopebtn").click(); await wait(60);
  ok("clicking the control again closes the menu", q("#scopemenu").hidden);
  q("#scopebtn").click(); await wait(60);
  document.body.click(); await wait(60);
  ok("clicking away closes the menu", q("#scopemenu").hidden);
  q("#scopebtn").click(); await wait(60);
  [...document.querySelectorAll("#scopemenu li")].find(li=>li.dataset.v==="all").click();
  await wait(80);
  ok("choosing from the menu sets the scope", q("#scope").value==="all");
  ok("and the control shows what was chosen",
     /todas/i.test(q("#scopelabel").textContent));
  q("#scope").value="name"; q("#scope").dispatchEvent(new Event("change")); await wait(60);
  ok("the label follows a scope set from elsewhere", /nome/i.test(q("#scopelabel").textContent));

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

  // the engine's decode score must not read as a claim that it got it right
  const dots=document.querySelectorAll("#rows .dot");
  ok("engine score shown as semaphore dots", dots.length>0);
  // `Brges. iuig` scored 0.86 and showed green. The number is the recogniser's
  // decode score, and it stays high on confident nonsense.
  ok("no dot calls the engine's score confidence",
     [...dots].every(d=>!/confian/i.test(d.getAttribute("aria-label")||"")));
  ok("a high score is not painted as a verified reading",
     [...document.querySelectorAll("#rows .dot.hi")].every(
       d=>!d.classList.contains("person")));
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

  const hiBefore=document.querySelectorAll(".dot.person").length;
  const ed=document.querySelector('#rows tr[data-i="4"] [data-f="nationality"]');
  if(ed){ ed.textContent="BELGA"; ed.dispatchEvent(new Event("input",{bubbles:true})); await wait();
    ok("a cell a person typed is marked as read by a person, not scored",
       document.querySelectorAll(".dot.person").length>hiBefore); }

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
  // Searching the corpus is a server call. Opened from disk the page has no
  // API to ask, so these assertions describe a run that cannot happen there —
  // and reporting them as failures buried the ones that mattered.
  if(cq && SERVED_RUN){
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
  if(SERVED_RUN){
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

  // An engine improvement has to be able to reach a document already in the
  // cache. Until now the only way was to delete its file by hand.
  {
    const b = document.getElementById("reread");
    ok("a document can be asked for again", !!b);
  }

  // A word the recogniser read two ways is offered as a choice rather than
  // left to be retyped. The alternatives are the engine's own output — the ink
  // mask reading and the render reading of the same band.
  {
    const saved = rows[0] && JSON.parse(JSON.stringify(rows[0]));
    if(rows[0]){
      rows[0].name_raw = "Nayomgo Cassaudii";
      rows[0].name_alts = [["Raymundo"], ["Cassaudie"]];
      render();
      const pills = document.querySelectorAll("#rows tr[data-i='0'] .altword");
      ok("a word read two ways is marked as changeable", pills.length === 2);
      if(pills.length){
        pills[0].click();
        await wait(80);
        const menu = document.querySelector(".altmenu");
        ok("clicking it offers the other reading",
           !!menu && menu.textContent.indexOf("Raymundo") >= 0);
        ok("and shows the reading it currently has",
           !!menu && menu.textContent.indexOf("Nayomgo") >= 0);
        const btns = menu ? [...menu.querySelectorAll("button")] : [];
        const pick = btns.find(b=>b.textContent === "Raymundo");
        if(pick){
          pick.click();
          await wait(120);
          ok("choosing it rewrites that word and leaves the other alone",
             rows[0].name_raw === "Raymundo Cassaudii");
          ok("and the row counts as checked by a person", rows[0].verified === true);
          ok("the menu closes after choosing", !document.querySelector(".altmenu"));
        }
      }
      // a word both readings agree on is not dressed up as a choice
      rows[0].name_alts = [[], []];
      render();
      ok("a word the readings agree on is left alone",
         !document.querySelector("#rows tr[data-i='0'] .altword"));
      Object.assign(rows[0], saved); render();
    }
  }

  // The name cell shows what the page says. It was showing the *split* of the
  // name put back together the other way round: BS.ENT.013990 reads `Raymundo
  // Cassaudii` and the row showed `Cassaudii Nayomgo`. A transcription that
  // reorders the document is asserting something the document does not say.
  {
    const row = {name_raw:"Nayomgo Cassaudii", surname:"Nayomgo", given:"Cassaudii"};
    ok("the name cell shows the reading verbatim", nameText(row) === "Nayomgo Cassaudii");
    ok("a row with no verbatim reading still shows a name",
       nameText({surname:"SILVA", given:"JOSE"}).indexOf("SILVA") >= 0);
    // same convention as desembarque/engine_paddle.py split_name
    ok("the split takes the given name last",
       String(splitName("ROCA REBULLIDA AMPARO")) === "ROCA REBULLIDA,AMPARO");
    ok("one word is a surname on its own",
       String(splitName("CASSAUDII")) === "CASSAUDII,");
  }

  // Beside the ship in the folder list, when she landed: that is how somebody
  // with an approximate date picks the handful of dossiers worth opening.
  {
    ok("a document that states no date gets no date in the list",
       typeof docYear === "function" && docYear({}) === "");
    ok("a document that states one shows it",
       docYear({meta:{arrival:"1924-12-10"}}).indexOf("1924-12-10") === 0);
    ok("a year without a full date is shown too",
       docYear({meta:{year:1925}}).indexOf("1925") === 0);
  }

  // The voyage line is built from whatever the dossier's form actually stated.
  // A fixed template printed "undefined" between the bullets for every field
  // the clerk left blank, which reads as a page that said nothing where the
  // page was never asked.
  {
    const saved = D && D.meta;
    if(typeof D !== "undefined" && D){
      D.meta = {ship:"Baden", year:1925, notation:"OL.PRJ.20039", source:"parte"};
      {
        const both = (D.meta = {ship:"Jaronna", catalog_ship:"garonne",
                                notation:"X", source:"lista"}) && docmetaLine();
        ok("the archive's name for the dossier leads", both.indexOf("garonne") >= 0);
        ok("and the reading off the page is kept beside it",
           both.indexOf("Jaronna") >= 0);
        D.meta = {ship:"Baden", catalog_ship:"baden", notation:"X"};
        ok("one name is shown once when the two agree",
           docmetaLine().split("baden").length - 1 <= 1);
      }
      D.meta = {ship:"Baden", year:1925, notation:"OL.PRJ.20039", source:"parte"};
      const line = docmetaLine();
      ok("the header names the ship the document names", line.indexOf("Baden") >= 0);
      ok("a field the page never stated is left out, not printed as undefined",
         line.indexOf("undefined") < 0 && line.indexOf("null") < 0);
      ok("a year without a full date is still shown", line.indexOf("1925") >= 0);
      D.meta = saved;
    }
  }

  // Correcting a record is deliberate. Every cell used to be editable all the
  // time, including the ones the engine never attempted, so the page invited
  // typing into fields that had simply not been read — and a stray keystroke on
  // a record meant as evidence is worse than one extra click.
  {
    const btn = document.getElementById("editmode");
    ok("an edit-mode toggle exists", !!btn);
    if(btn){
      ok("editing is off until asked for", btn.getAttribute("aria-pressed") === "false");
      ok("cells are not editable while it is off",
         !document.querySelector('#rows span[contenteditable="true"]'));
      btn.click();
      await wait(150);
      ok("turning it on makes cells editable",
         !!document.querySelector('#rows span[contenteditable="true"]'));
      ok("and the page shows that it is on", document.body.classList.contains("editing"));
      btn.click();
      await wait(150);
      ok("turning it off puts the page back to read-only",
         !document.querySelector('#rows span[contenteditable="true"]'));
    }
    const ex = document.getElementById("exportcsv");
    ok("an export control exists", !!ex);
    if(ex) ok("export points at the served document or is disabled",
              (ex.getAttribute("href")||"").indexOf("/api/export") === 0
              || ex.getAttribute("aria-disabled") === "true");
  }

 }catch(err){ out.push("THREW "+(err&&err.message)); }
 document.getElementById("warn").textContent="RESULTS>> "+out.join(" | ");
});
