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
  ok("unreadable shown as ilegivel", document.querySelectorAll("#rows td.null").length>0);
  ok("ditto marked", document.querySelectorAll("#rows td.ditto").length>0);

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
             [...document.querySelectorAll('#rows td[data-f="nationality"]')]
               .every(td=>/^\s*(ilegível)?\s*$/.test(td.textContent)));
        }
      }
    }
  }
 }catch(err){ out.push("THREW "+(err&&err.message)); }
 document.getElementById("warn").textContent="RESULTS>> "+out.join(" | ");
});
