'use strict';
const $ = id => document.getElementById(id);
let data = {jobs: [], sources: [], catalog: [], refresh: {}}, view = 'discover', selected = null, loaded = false;
const labels = {discovered: 'New', saved: 'Saved', applied: 'Applied', interviewing: 'Interviewing', offer: 'Offer', rejected: 'Rejected', withdrawn: 'Withdrawn'};
const date = value => value ? new Date(value).toLocaleDateString(undefined, {month:'short', day:'numeric'}) : '—';
function node(tag, text, cls) {const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if(cls) el.className = cls; return el;}
function renderDirectory() {
  const health = new Map(data.sources.map(s=>[s.company,s]));
  const category = $('directory-category').value, status = $('directory-status').value;
  const query = $('directory-search').value.toLowerCase().trim();
  const companies = data.catalog.filter(company => {
    const source = health.get(company.name), state = source?.state || (company.provider === 'manual' ? 'manual' : 'pending');
    const group = state === 'manual' ? 'manual' : state === 'error' ? 'error' : 'automatic';
    return (!category || company.category === category) && (!status || status === group) &&
      (!query || `${company.name} ${company.category || ''} ${company.location || ''}`.toLowerCase().includes(query));
  });
  $('source-count').textContent = `${companies.length} of ${data.catalog.length} companies`;
  $('sources').replaceChildren();
  for (const company of companies) {
    const source = health.get(company.name), state = source?.state || (company.provider === 'manual' ? 'manual' : 'pending');
    const detail = source?.detail || (state === 'manual' ? 'Official careers page — check manually' : 'Automatic feed — awaiting first refresh');
    const row=node('div',undefined,'source'), link=node('a','Open careers ↗');
    link.href=company.careers_url;link.target='_blank';link.rel='noopener noreferrer';
    row.append(node('strong',company.name),node('span',`${company.category || 'Aerospace'}${company.location ? ` · ${company.location}` : ''}`,'source-location muted'),node('span',detail,state==='error'?'source-error':state==='manual'?'source-manual':'muted'),link);
    $('sources').append(row);
  }
  if (!companies.length) $('sources').append(node('p','No companies match these filters.','muted'));
}
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-App-Token':data.token},body:JSON.stringify(body)});
  const result = await response.json();
  if(!response.ok) throw new Error(result.error || 'Something went wrong. Please retry.');
  return result;
}
function render() {
  const jobs = data.jobs;
  $('open-count').textContent = jobs.filter(j=>j.active).length;
  $('saved-count').textContent = jobs.filter(j=>j.status==='saved').length;
  $('applied-count').textContent = jobs.filter(j=>['applied','interviewing'].includes(j.status)).length;
  $('offer-count').textContent = jobs.filter(j=>j.status==='offer').length;
  $('refresh').disabled = !!data.refresh.running;
  $('refresh').textContent = data.refresh.running ? '↻ Checking job boards…' : '↻ Refresh jobs';
  const automaticCompanies = new Set(data.catalog.filter(c=>c.provider!=='manual').map(c=>c.name));
  const errors = data.sources.filter(s=>s.state==='error' && automaticCompanies.has(s.company)).length;
  $('notice').textContent = data.refresh.error || (data.refresh.running ? 'Checking company boards. You can keep browsing while jobs arrive.' : errors ? `${errors} automatic feeds need attention. Open Company directory for details.` : '');
  $('sync').textContent = data.refresh.last_finished ? `Last refresh ${new Date(data.refresh.last_finished).toLocaleString()} · ${data.refresh.added} new matches` : 'Refreshes every 6 hours by default while the app is running';
  $('jobs-section').hidden = view==='sources'; $('sources-section').hidden = view!=='sources';
  $('heading').textContent = {discover:'Find your launchpad.',tracker:'Keep your future in flight.',sources:'Go beyond the primes.'}[view];
  $('subtitle').textContent = {discover:'Internships and co-ops for the next generation of aerospace engineers.',tracker:'A home for your shortlist, applications, and next steps.',sources:'Launch, aviation, defense, autonomy, suppliers, and the small teams between them.'}[view];
  $('breadcrumb').textContent = {discover:'Discover',tracker:'Application tracker',sources:'Company directory'}[view];
  $('list-title').textContent = view==='tracker' ? 'Your application pipeline' : 'Explore opportunities';
  const company = $('company').value;
  $('company').replaceChildren(new Option('All companies',''), ...[...new Set(jobs.map(j=>j.company))].sort().map(c=>new Option(c,c)));
  $('company').value = company;
  const query = $('search').value.toLowerCase().trim();
  const filtered = jobs.filter(j=>(view!=='tracker'||j.status!=='discovered') && (view==='tracker'||$('closed').checked||j.active) && (!company||j.company===company) && (!$('stage').value||j.status===$('stage').value) && (!query||`${j.title} ${j.company} ${j.location}`.toLowerCase().includes(query)));
  $('result-count').textContent = `${filtered.length} opportunities`;
  $('jobs').replaceChildren();
  for(const job of filtered) {
    const card = node('article',undefined,'job'), top = node('div',undefined,'card-top');
    top.append(node('div',job.company.split(' ').map(s=>s[0]).join('').slice(0,2),'avatar'),node('span',job.company,'company-name'),node('span',job.active?labels[job.status]:'Closed','badge'));
    const bottom = node('div',undefined,'card-bottom'), actions = node('div');
    const detail = node('button','Details ↗','text-button'); detail.onclick=()=>openJob(job.id); actions.append(detail);
    if(job.status==='discovered') {const save = node('button','＋ Save','secondary');save.onclick=async()=>{save.disabled=true;try{await api(`/api/jobs/${job.id}`,{status:'saved',notes:job.notes});await load();}catch(e){$('notice').textContent=e.message;save.disabled=false;}};actions.append(save);}
    bottom.append(node('span',`First found ${date(job.first_seen)}`),actions);
    card.append(top,node('h3',job.title),node('div',`⌖ ${job.location}`,'location'),bottom);$('jobs').append(card);
  }
  if(!filtered.length) {const empty=node('div',undefined,'empty');empty.append(node('h3',view==='tracker'?'Your next chapter goes here.':'Ready for takeoff.'),node('p',jobs.length?'No jobs match this view. Try changing your filters, or save an opportunity from Discover.':'Refresh to find internships from company job boards. Listings will appear here as sources finish. Check Company directory if a board is unavailable.'));$('jobs').append(empty);}
  renderDirectory();
}
function openJob(id){selected=id;const j=data.jobs.find(j=>j.id===id);$('detail-company').textContent=j.company;$('detail-title').textContent=j.title;$('detail-location').textContent=j.location;$('detail-stage').value=j.status;$('notes').value=j.notes;$('save-error').textContent='';$('apply-link').href=j.url.startsWith('https://')?j.url:'#';$('network-link').href=`https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(j.company)}`;$('detail-dates').textContent=`First found ${date(j.first_seen)} · Last seen ${date(j.last_seen)}${j.active?'':' · No longer listed on last successful check'}`;$('detail').showModal();}
async function load(){try{data=await api('/api/state');const chosen=$('directory-category').value;$('directory-category').replaceChildren(new Option('All sectors',''),...[...new Set(data.catalog.map(c=>c.category).filter(Boolean))].sort().map(c=>new Option(c,c)));$('directory-category').value=chosen;loaded=true;render();}catch(e){$('notice').textContent=loaded?'Cannot reach the app. Keep its terminal window open, then reload.':e.message;}}
document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>{view=button.dataset.view;document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-current',b===button?'page':'false');});render();});
['search','company','stage','closed'].forEach(id=>$(id).addEventListener('input',render));
['directory-search','directory-status'].forEach(id=>$(id).addEventListener('input',renderDirectory));
$('directory-category').addEventListener('input',renderDirectory);
$('refresh').onclick=async()=>{try{$('refresh').disabled=true;await api('/api/refresh',{});await load();}catch(e){$('notice').textContent=e.message;$('refresh').disabled=false;}};
$('close').onclick=()=>$('detail').close();
$('detail-form').onsubmit=async event=>{event.preventDefault();$('save-detail').disabled=true;try{await api(`/api/jobs/${selected}`,{status:$('detail-stage').value,notes:$('notes').value});$('detail').close();await load();}catch(e){$('save-error').textContent=e.message;}finally{$('save-detail').disabled=false;}};
load();setInterval(load,10000);
