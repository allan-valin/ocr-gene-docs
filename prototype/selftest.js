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
function sel_of(){ const on=document.querySelector("#rows tr.sel"); return on?on.dataset.i:null; }
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
  // the sample's rows arrive with the corpus, which on a loaded machine can be
  // a second behind the page being ready
  for(let i=0;i<40 && document.querySelectorAll("#rows tr").length!==26;i++) await wait(150);
  ok("rows rendered=26", document.querySelectorAll("#rows tr").length===26);
  ok("scan image loaded", q("#scan").naturalWidth>0);
  ok("band painted", !q("#bandBox").hidden && parseFloat(q("#bandBox").style.height)>0);
  ok("scope defaults to name", q("#scope").value==="name");
  // Every other document in the app shows names and nothing else, because
  // names are all the engine reads. Somebody who opens this one first and a
  // real dossier second sees a tool that stopped working, unless the page says
  // what this one is.
  ok("the demo says its columns were typed by a person",
     !!q("#handnote") && !q("#handnote").hidden
     && /pessoa/i.test(q("#handnote").textContent));

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
  // The cell shows *Schrader* now — the reading is unchanged, the shouting is
  // not how a name is read — so the row is matched without regard to case.
  ok("variant: joao finds SCHRADER", [...document.querySelectorAll("#rows tr.hit")].some(t=>/schrader/i.test(t.textContent)));
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
  // A surname read off a repetition mark is what the page says; one taken from
  // the row above because this row had none is an inference, and a registrar
  // reading the table has to be able to tell them apart.
  // The sample page carries one of each; a real dossier need not, so the
  // existence check belongs to the built page and the labelling check to both.
  ok("an inferred surname is marked as inferred, not as read",
     SERVED_RUN || document.querySelectorAll("#rows .ditto.guessed").length>0);
  ok("a surname off the mark is not marked as inferred",
     [...document.querySelectorAll("#rows .ditto")].some(e=>!e.classList.contains("guessed")));
  ok("the inference says so when you hover it",
     [...document.querySelectorAll("#rows .ditto.guessed")]
       .every(e=>/inferido/i.test(e.getAttribute("title")||"")));

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
  // Names the archive knows, offered for a mangled word: guesses, and shown as
  // guesses, in their own labelled section. They used to be off until asked
  // for, which meant a reader clicking a word was shown the engine's own two
  // readings and nothing else — and the button that would have helped had no
  // visible effect until some later click on some other word. On by default,
  // and the button must agree with the state it is actually in.
  ok("probable names are offered without hunting for a switch",
     q("#guessbtn").getAttribute("aria-pressed")==="true");
  ok("the ordering toggle is available with them", !q("#guessfirst").hidden);
  if(SERVED_RUN){
    const pill=document.querySelector("#rows .altword");
    if(pill){
      pill.click(); await wait(600);
      const menu=document.querySelector(".altmenu");
      ok("the menu still offers what the engine read",
         !!menu && /leituras do motor/.test(menu.textContent));
      ok("a guess is labelled as not read from the page",
         !menu || !menu.querySelector("button.guess")
         || /não lidos da página/.test(menu.textContent));
      closeAltMenu ? closeAltMenu() : document.body.click();
    }
  }
  q("#guessbtn").click(); await wait(40);
  ok("they can be turned off", q("#guessbtn").getAttribute("aria-pressed")==="false");
  ok("and turning them off hides the ordering toggle", q("#guessfirst").hidden);
  q("#guessbtn").click(); await wait(40);
  ok("and back on", q("#guessbtn").getAttribute("aria-pressed")==="true");

  // Which rows to look at first, when a dossier has four hundred of them.
  ok("doubtful rows are off until asked for",
     q("#doubtbtn").getAttribute("aria-pressed")==="false"
     && !document.querySelector("#rows tr.doubt"));
  if(SERVED_RUN){
    q("#doubtbtn").click(); await wait(700);
    ok("asking marks them, or says none were found",
       q("#doubtbtn").getAttribute("aria-pressed")==="true");
    const marked=[...document.querySelectorAll("#rows tr.doubt")];
    ok("a marked row says why it is marked",
       marked.every(tr=>/motor|inferido|acervo/.test(tr.getAttribute("title")||"")));
    ok("a way to walk them appears with them", !q("#nextdoubt").hidden);
    const before=sel_of();
    q("#nextdoubt").click(); await wait(120);
    ok("walking them lands somewhere and says where",
       /duvidosa|nenhuma linha duvidosa/.test(q("#nextdoubt").dataset.at||""));
    q("#doubtbtn").click(); await wait(200);
    ok("and they can be cleared", !document.querySelector("#rows tr.doubt"));
    ok("the walk control goes with them", q("#nextdoubt").hidden);
  }

  // The hit list shows twenty-five; somebody tracing an ancestor needs all of
  // them, with the notation and the line to ask the archive for.
  if(SERVED_RUN){
    // the corpus box, not the in-document one: this searches everything indexed
    // the corpus box is handled at document level, so the event has to bubble
    q("#corpusq").value="silva";
    q("#corpusq").dispatchEvent(new Event("input",{bubbles:true}));
    // the corpus index is loaded on the first search and the machine may be
    // reading pages at the same time
    for(let i=0;i<120 && !document.querySelector("#corpushits .hit");i++) await wait(250);
    const narrow=document.querySelector("#corpushits .hit .narrow");
    if(narrow){
      const ship=narrow.dataset.ship;
      narrow.click(); await wait(300);
      ok("a hit can ask again with its ship named",
         (q("#corpusq").value||"").toLowerCase().includes((ship||"").toLowerCase()));
      q("#corpusq").value="silva";
      q("#corpusq").dispatchEvent(new Event("input",{bubbles:true}));
      for(let i=0;i<40 && !document.querySelector("#corpushits .hit");i++) await wait(150);
    }
    const dl=document.querySelector("a.dlhits");
    ok("the results can be taken away as a spreadsheet", !!dl);
    ok("and the download asks for the query that produced them",
       !dl || /\/api\/export\/search\?q=silva/.test(dl.getAttribute("href")||""));
    q("#corpusq").value="";
    q("#corpusq").dispatchEvent(new Event("input",{bubbles:true})); await wait(80);
  }

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
    // Typing only a name finds 49 of 100 hand-read cursive names and naming the
    // crossing finds 81, so a weak result list has one useful thing to say.
    cq.value="kowalczyk"; cq.dispatchEvent(new Event("input",{bubbles:true}));
    let advised=false;
    for(let i=0;i<24 && !advised;i++){
      await wait(200);
      const box=document.getElementById("corpushits");
      advised = !!box.querySelector(".advice")
             || !box.querySelector(".hit");   // nothing at all is also an answer
    }
    ok("a weak result list says to name the ship, the company or the year", advised);
    cq.value="amparo"; cq.dispatchEvent(new Event("input",{bubbles:true}));
    for(let i=0;i<24;i++){
      await wait(200);
      if(document.querySelectorAll("#corpushits .hit").length) break;
    }
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
      // While a run is going the bar offers "Parar" instead: the control that
      // has to exist is the one for the state the folder is actually in.
      const btn=document.getElementById("doindex")||document.getElementById("stopindex");
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
      // A word both readings agree on used to be left plain, which made the
      // archive's names unreachable for it: `Yosé`, read once and wrongly, had
      // nothing to click. Every word opens its readings now; only the ones the
      // engine itself read two ways carry the caret.
      rows[0].name_alts = [[], []];
      render();
      const plain = document.querySelector("#rows tr[data-i='0'] .altword");
      ok("a word the engine read once can still be questioned", !!plain);
      ok("but it is not dressed up as a disagreement",
         !!plain && !plain.classList.contains("twice"));
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
    // Somebody opens the other readings of a word, looks, and wants none of
    // them. Clicking the word again rebuilt the menu under the cursor instead
    // of putting it away, so the only way out was to click elsewhere and hope
    // nothing else took the click.
    {
      // The demo document is a hand transcription, so it carries no engine
      // alternates and no pill: this covers the served app, where they exist.
      const pill = document.querySelector("#rows .altword");
      if(pill){
        const before = pill.textContent;
        pill.click();
        await wait(120);
        ok("clicking a word opens its readings", !!document.querySelector(".altmenu"));
        pill.click();
        await wait(120);
        ok("clicking the same word again closes them",
           !document.querySelector(".altmenu"));
        ok("and closing them changes nothing", pill.textContent === before);
      }
    }
    // A name read off a page is shown as a name. The reading is not rewritten
    // — this is the cell, not the record — and the particles these lists
    // actually use stay lower case.
    ok("a name is shown capitalised, not shouted",
       typeof displayName === "function" && displayName("ROCA REBULLIDA AMPARO")
       === "Roca Rebullida Amparo");
    ok("and the particles the clerks wrote stay small",
       typeof displayName === "function"
       && displayName("da silva DOS SANTOS") === "da Silva dos Santos");
    ok("a reading is never rewritten by the way it is shown",
       typeof nameText === "function"
       && nameText({name_raw: "alfieri"}) === "alfieri");
    // Rows 19 to 24 of BS.ENT.013947 are stored `"Maria`, `"angeta`: the mark
    // is what the page says and belongs in the record, but on screen it is a
    // mark and not a letter of somebody's name.
    ok("a repetition mark is shown as a mark, not glued to the name",
       typeof nameCell === "function"
       && /class="ditto"/.test(nameCell({name_raw: '"Maria'}))
       && />Maria</.test(nameCell({name_raw: '"Maria'})));

    // A value in one of the other columns is either somebody's typing or the
    // engine's word, and on screen they looked identical. The engine has never
    // written those columns — two rows of BS.ENT.013942 carry a profession and
    // a nationality a person typed at the review screen — so a value that came
    // from a person has to say so.
    ok("a value a person typed says it was typed",
       typeof cell === "function"
       && /class="[^"]*typed/.test(cell({occupation: "SIRVIENTA",
                                         edits: [{field: "occupation",
                                                  to: "SIRVIENTA"}]},
                                        "occupation", "SIRVIENTA")));
    ok("and a value the engine read carries no such claim",
       typeof cell === "function"
       && !/class="[^"]*typed/.test(cell({nationality: "BELGA"},
                                         "nationality", "BELGA")));

    // Measured: the first guess is the right name for 51 of 217 badly-read
    // words and the engine's own second reading for 6, so the guesses are the
    // top of the menu unless somebody says otherwise.
    ok("the guesses are offered first", typeof GUESSES_FIRST !== "undefined"
       && GUESSES_FIRST === true);
    ok("and the control says so",
       !!q("#guessfirst") && q("#guessfirst").getAttribute("aria-pressed") === "true");

    // Reading the faint pages by eye. The recogniser is at its ceiling on a
    // hundred-year-old hand and a person is not, so the reader needs the paper
    // out of the way rather than a better guess about it.
    const tools = q("#scantools");
    ok("the scan can be enhanced for a person to read", !!tools);
    if(tools && typeof setEnhance === "function"){
      const img = q("#scan");
      setEnhance("realce");
      ok("a realce is applied to the scan itself",
         img.getAttribute("data-enhance") === "realce");
      ok("and the control shows which one is on",
         q("#enh-realce").getAttribute("aria-pressed") === "true"
         && q("#enh-original").getAttribute("aria-pressed") === "false");
      setEnhance("negativo");
      ok("the negative is available, where faint grey on grey becomes light on black",
         img.getAttribute("data-enhance") === "negativo");
      setEnhance("");
      ok("and the original comes back untouched",
         !img.hasAttribute("data-enhance")
         && q("#enh-original").getAttribute("aria-pressed") === "true");
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
