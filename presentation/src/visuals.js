(function(root){
  'use strict';
  const C={ink:'#17263c',blue:'#2459c4',coral:'#c34d35',green:'#16704e',purple:'#7254ad',gray:'#607187',line:'#cbd5e2',pale:'#edf3fc',warm:'#fff0e9'};
  const e=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const n=(v,d=0)=>v==null?'N/A':Number(v).toLocaleString('vi-VN',{minimumFractionDigits:d,maximumFractionDigits:d});
  const p=v=>v==null?'N/A':n(v*100,2)+'%';
  const tx=(x,y,s,cls='s-body',extra='')=>`<text x="${x}" y="${y}" class="${cls}" ${extra}>${e(s)}</text>`;
  const lines=(x,y,list,cls='s-body',gap=29,extra='')=>list.map((s,i)=>tx(x,y+i*gap,s,cls,extra)).join('');
  const frame=(body,label,w=1200,h=370)=>`<div class="scene"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="${e(label)}"><title>${e(label)}</title><defs><marker id="arrow-tip" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 1L8 5L0 9" fill="none" stroke="context-stroke" stroke-width="1.6"/></marker><pattern id="soft-grid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#dce5f0"/></pattern></defs>${body}</svg></div>`;
  const rect=(x,y,w,h,fill='#edf3fc',r=18,extra='')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" ${extra}/>`;
  const circle=(x,y,r,fill,extra='')=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" ${extra}/>`;
  const edge=(d,color=C.line,animate=false)=>`<path d="${d}" fill="none" stroke="${color}" stroke-width="3" marker-end="url(#arrow-tip)" class="${animate?'signal-line':''}"/>`;
  function pulse(d,color=C.blue,delay=0){return `<circle r="5" fill="${color}" class="moving-packet"><animateMotion dur="3s" begin="${delay}s" repeatCount="indefinite" path="${d}"/></circle>`;}
  function icon(kind,x,y,size=64,color=C.blue){
    const paths={
      data:'M12 16C12 7 52 7 52 16S12 25 12 16V46C12 57 52 57 52 46V16M12 30C12 40 52 40 52 30',
      clean:'M12 16H52M18 30H46M25 44H39M45 43L51 49L60 36',
      split:'M31 5V25M31 25L10 40V56M31 25L52 40V56M31 25V56',
      features:'M9 12H18V55H9ZM28 26H37V55H28ZM47 5H56V55H47Z',
      normalize:'M5 50H59M8 49C20 49 17 14 31 14S42 49 56 49M31 8V55',
      select:'M8 10H56L38 32V51L26 57V32Z',
      train:'M10 14L32 8L54 18L49 45L29 56L10 43ZM10 14L29 31L54 18M10 43L29 31L49 45M32 8L29 31L29 56',
      results:'M8 7V56H59M17 43L29 31L39 38L55 17M46 17H55V26',
      conclusion:'M32 6A26 26 0 1 0 58 32M20 31L29 40L54 13',
      server:'M8 9H56V24H8ZM8 28H56V43H8ZM8 47H56V59H8ZM15 16H18M15 35H18M15 53H18M37 16H49M37 35H49',
      lock:'M16 28H48V57H16ZM23 28V18C23 4 42 4 42 18V28M32 39V47',
      clock:'M32 6A26 26 0 1 0 32 58A26 26 0 1 0 32 6M32 16V32L43 40',
      shield:'M32 5L54 14V31C54 46 41 55 32 60C23 55 10 46 10 31V14ZM21 31L29 39L44 23'
    };
    return `<g transform="translate(${x},${y}) scale(${size/64})" fill="none" stroke="${color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[kind]||paths.data}"/></g>`;
  }
  function grid(x,y,cols=8,rows=8,size=10,gap=3,accent=C.blue,extra=''){
    return `<g ${extra}>${Array.from({length:cols*rows},(_,i)=>rect(x+(i%cols)*(size+gap),y+Math.floor(i/cols)*(size+gap),size,size,i%5===0?accent:i%3===0?'#9db7e6':'#dbe6f8',2)).join('')}</g>`;
  }
  const note=(message,kind='')=>`<p class="visual-note ${kind}">${e(message)}</p>`;
  const chips=items=>`<div class="semantic-tags">${items.map(s=>`<span>${e(s)}</span>`).join('')}</div>`;
  const select=(key,label,options,value)=>`<label class="chart-select"><span>${e(label)}</span><select data-control="${key}">${options.map(([k,s])=>`<option value="${e(k)}" ${k===value?'selected':''}>${e(s)}</option>`).join('')}</select></label>`;
  const controls=(...children)=>`<div class="chart-controls">${children.join('')}</div>`;
  const phases=(names,current=0)=>`<div class="phase-controls" role="group" aria-label="Các phần minh họa">${names.map((s,i)=>`<button data-action="phase" data-value="${i}" aria-pressed="${i===current}"><span>${String(i+1).padStart(2,'0')}</span>${e(s)}</button>`).join('')}</div>`;
  const metricInfo={f1_macro_present:'F1-macro-present',dos_f1:'F1 DoS/DDoS',attack_f1:'F1 mọi tấn công',attack_recall:'Recall mọi tấn công',dos_recall:'Recall DoS/DDoS',attack_far_benign:'FAR mọi tấn công ↓',acc:'Accuracy',attack_roc_auc:'AUC mọi tấn công'};
  const sources={mean_over_sources:'Trung bình hai nguồn',cicddos2019:'CIC-DDoS2019',unsw_nb15:'UNSW-NB15',worst_source:'Kém nhất theo từng chỉ số',pooled_predictions:'Dự đoán gộp'};
  const labels={all:'FedAvg · ALL',das:'FedAvg · DAS',prox:'FedProx · DAS',central:'Centralized',local_c1:'Local · CIC #1',local_c2:'Local · CIC #2',local_c3:'Local · UNSW #3',local_c4:'Local · UNSW #4'};
  const colors={all:'#607187',das:C.blue,prox:C.green,central:C.purple,local_c1:C.coral,local_c2:'#e08a6f',local_c3:'#a07322',local_c4:'#c9a35a'};
  const LOCALS=['local_c1','local_c2','local_c3','local_c4'];
  const keyMetrics=value=>select('metric','Chỉ số',Object.entries(metricInfo),value);
  const keySource=value=>select('source','Tập đánh giá',Object.entries(sources).filter(([k])=>!['worst_source','pooled_predictions'].includes(k)),value);

  const compareTable=(headers,rows,after=-1)=>`<div class="compare-table"><table><thead><tr>${headers.map((h,i)=>`<th scope="col" class="${i===after?'after':''}">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((c,i)=>i===0?`<th scope="row" class="${i===after?'after':''}">${c}</th>`:`<td class="${i===after?'after':''}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  function create(ctx){
    const {data,content,groups,byId,row,assets={}}=ctx;
    const phase=state=>Number(state.phase||0);
    const stat=(value,label,detail='')=>`<div class="editorial-stat"><strong>${e(value)}</strong><span>${e(label)}</span>${detail?`<small>${e(detail)}</small>`:''}</div>`;
    function heroNetwork(){
      const R='repeatCount="indefinite"',SX=1235,SY=450,G='#5ee2a0';
      const clients=[[990,262,'#6aa8ff','Client 1 · CIC'],[985,640,'#6aa8ff','Client 2 · CIC'],[1490,262,'#ff8a6a','Client 3 · UNSW'],[1500,640,'#ff8a6a','Client 4 · UNSW']];
      const deco=[[120,170],[260,330],[90,560],[330,700],[520,150],[600,420],[470,600],[700,260],[760,760],[1020,130],[1300,110],[1560,420],[1320,780],[1040,800],[640,880],[200,820],[1580,140],[1590,760]];
      let b=`<defs>
        <radialGradient id="h-core" cx="50%" cy="40%" r="60%"><stop offset="0" stop-color="#7ef0b8"/><stop offset="1" stop-color="#1c8f5c"/></radialGradient>
        <radialGradient id="h-halo"><stop offset="0" stop-color="#3fd39a" stop-opacity=".45"/><stop offset="1" stop-color="#3fd39a" stop-opacity="0"/></radialGradient>
        <filter id="h-glow" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="5"/></filter>
        <pattern id="h-dots" width="34" height="34" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.3" fill="#ffffff" opacity=".07"/></pattern>
        <linearGradient id="h-fade" x1="0" x2="1"><stop offset="0" stop-color="#0a1830" stop-opacity=".92"/><stop offset=".42" stop-color="#0a1830" stop-opacity=".55"/><stop offset=".62" stop-color="#0a1830" stop-opacity="0"/></linearGradient>
      </defs><rect width="1600" height="900" fill="url(#h-dots)"/>`;
      // decorative mesh
      deco.forEach(([x,y],k)=>{const [nx,ny]=deco[(k+3)%deco.length];b+=`<line x1="${x}" y1="${y}" x2="${nx}" y2="${ny}" stroke="#7fa7e8" stroke-opacity=".10" stroke-width="1"/>`;});
      deco.forEach(([x,y],k)=>{b+=`<circle cx="${x}" cy="${y}" r="${3+k%3}" fill="#9cc0ff" opacity=".35"><animate attributeName="opacity" values=".15;.55;.15" dur="${3+k%4}s" begin="${-k*0.7}s" ${R}/></circle>`;});
      // links + particles
      clients.forEach(([x,y,col],k)=>{
        const mx=(SX+x)/2+(k<2?-40:40),my=(SY+y)/2+(y<SY?-60:60),d=`M${SX},${SY} Q${mx},${my} ${x},${y}`,du=`M${x},${y} Q${mx},${my} ${SX},${SY}`;
        b+=`<path d="${d}" fill="none" stroke="#ffffff" stroke-opacity=".16" stroke-width="2"/>`;
        b+=`<path d="${d}" fill="none" stroke="${col}" stroke-opacity=".5" stroke-width="2" stroke-dasharray="3 14"><animate attributeName="stroke-dashoffset" from="0" to="-34" dur="1.4s" ${R}/></path>`;
        for(let q=0;q<3;q++){
          b+=`<g><circle r="11" fill="${G}" opacity=".55" filter="url(#h-glow)"/><circle r="5" fill="#eafff4"/><animateMotion dur="2.8s" begin="${-q*0.93-k*0.2}s" ${R} path="${d}" calcMode="spline" keyTimes="0;1" keySplines="0.45 0 0.3 1"/></g>`;
          b+=`<g><circle r="11" fill="${col}" opacity=".6" filter="url(#h-glow)"/><circle r="5" fill="#ffffff"/><animateMotion dur="2.8s" begin="${-q*0.93-k*0.2-0.46}s" ${R} path="${du}" calcMode="spline" keyTimes="0;1" keySplines="0.45 0 0.3 1"/></g>`;
        }
      });
      // server
      b+=`<circle cx="${SX}" cy="${SY}" r="230" fill="url(#h-halo)"/>`;
      for(let q=0;q<2;q++)b+=`<circle cx="${SX}" cy="${SY}" r="70" fill="none" stroke="${G}" stroke-width="2"><animate attributeName="r" values="70;260" dur="4s" begin="${-q*2}s" ${R}/><animate attributeName="opacity" values=".55;0" dur="4s" begin="${-q*2}s" ${R}/></circle>`;
      b+=`<g><circle cx="${SX}" cy="${SY}" r="118" fill="none" stroke="#9fe9c6" stroke-opacity=".45" stroke-width="1.5" stroke-dasharray="2 10"/><circle cx="${SX+118}" cy="${SY}" r="5" fill="#9fe9c6"/><animateTransform attributeName="transform" type="rotate" from="0 ${SX} ${SY}" to="360 ${SX} ${SY}" dur="18s" ${R}/></g>`;
      b+=`<g><circle cx="${SX}" cy="${SY}" r="150" fill="none" stroke="#7fa7e8" stroke-opacity=".3" stroke-width="1.2" stroke-dasharray="14 10"/><circle cx="${SX}" cy="${SY-150}" r="4" fill="#cfe0ff"/><animateTransform attributeName="transform" type="rotate" from="360 ${SX} ${SY}" to="0 ${SX} ${SY}" dur="26s" ${R}/></g>`;
      b+=`<circle cx="${SX}" cy="${SY}" r="72" fill="url(#h-core)" stroke="#c9ffe4" stroke-width="2.5"/>`+icon('train',SX-34,SY-38,68,'#ffffff');
      b+=`<text x="${SX}" y="${SY+108}" text-anchor="middle" class="h-label strong">Mô hình toàn cục</text><text x="${SX}" y="${SY+132}" text-anchor="middle" class="h-label">FedAvg / FedProx</text>`;
      // clients
      clients.forEach(([x,y,col,name])=>{
        b+=`<circle cx="${x}" cy="${y}" r="58" fill="${col}" opacity=".12"><animate attributeName="r" values="46;62;46" dur="3.2s" ${R}/></circle>`;
        b+=`<circle cx="${x}" cy="${y}" r="40" fill="#10264a" stroke="${col}" stroke-width="2.5"/>`+icon('server',x-20,y-20,40,col);
        const ly=y<SY?y-62:y+76;
        b+=`<rect x="${x-82}" y="${ly-22}" width="164" height="32" rx="16" fill="#0d2142" stroke="${col}" stroke-opacity=".6"/><text x="${x}" y="${ly}" text-anchor="middle" class="h-label strong">${e(name)}</text>`;
      });
      b+=`<rect width="1600" height="900" fill="url(#h-fade)"/>`;
      return `<svg class="hero-bg" viewBox="0 0 1600 900" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">${b}</svg>`;
    }
    function home(){
      const logo=assets.logo?`<img src="${assets.logo}" alt="Logo Trường Đại học Bách khoa – Đại học Đà Nẵng" width="88" height="88">`:'';
      return `<section class="hero">${heroNetwork()}<div class="hero-content">
        <div class="ts-school">${logo}<div><b>ĐẠI HỌC ĐÀ NẴNG</b><span>TRƯỜNG ĐẠI HỌC BÁCH KHOA</span><small>KHOA CÔNG NGHỆ THÔNG TIN</small></div></div>
        <h1>Học liên kết<br><em>phát hiện tấn công mạng</em></h1>
        <p class="ts-sub">trên hai nguồn dữ liệu CIC-DDoS2019 và UNSW-NB15</p>
        <dl class="ts-people"><div><dt>Giảng viên hướng dẫn</dt><dd>PGS.TS Nguyễn Tấn Khôi</dd></div><div><dt>Sinh viên thực hiện</dt><dd>Phan Văn Hiếu<span>MSSV 102230120</span></dd><dd>Đoàn Ngọc Minh<span>MSSV 102230157</span></dd></div></dl>
        <span class="hero-date">Đà Nẵng, 11/2026</span>
      </div></section>`;
    }
    function roadmap(){
      const positions=[[80,50],[340,50],[600,50],[860,50],[1120,50],[1120,210],[773,210],[427,210],[80,210]];
      const names=[['Tổng quan','dữ liệu'],['Làm sạch','& đồng nhất'],['Phân chia','dữ liệu'],['Xây dựng','đặc trưng'],['Chuẩn hóa','dữ liệu'],['Lựa chọn','đặc trưng'],['Kiến trúc','& huấn luyện'],['Đánh giá','kết quả'],['Kết luận','& hướng đi']];
      let body='';
      for(let i=0;i<8;i++){
        const [x,y]=positions[i],[nx,ny]=positions[i+1];
        const d=i===4?`M${x},${y+40} C${x+80},${y+70} ${nx+80},${ny-70} ${nx},${ny-40}`:i<4?`M${x+48},${y} L${nx-48},${ny}`:`M${x-48},${y} L${nx+48},${ny}`;
        body+=edge(d,'#b6c8e0',true);
      }
      groups.forEach(g=>{
        const i=content.stages.findIndex(s=>s.id===g.id),[x,y]=positions[i],kind=['data','clean','split','features','normalize','select','train','results','conclusion'][i];
        body+=`<a href="#${g.slides[0].id}" class="pipeline-stop" style="--order:${i}" aria-label="${e(g.title)}">${circle(x,y,39,i===7?'#e2efff':'#f1f5fb','class="stop-disc"')}${icon(kind,x-22,y-22,44,i===7?C.coral:C.blue)}${tx(x-54,y-35,String(i+1).padStart(2,'0'),'s-stage-index')}${lines(x,y+63,names[i],'s-pipeline-title',24,'text-anchor="middle"')}</a>`;
      });
      return `<section class="roadmap"><header class="roadmap-head"><h1>Quy trình thực hiện</h1><span>9 giai đoạn</span></header><section class="pipeline-map">${frame(body,'Pipeline chín giai đoạn',1200,300)}</section><div class="cover-bottom"><span>ResVGG-SwinNet · FedAvg · DAS · FedProx</span></div></section>`;
    }

    function bars(keys,metric,source){
      const x0=285,cw=755,top=47,step=keys.length>4?56:73,bh=keys.length>4?32:37,h=top+keys.length*step+20;
      let body='';
      for(let t=0;t<=4;t++){
        const x=x0+t*cw/4;body+=`<line x1="${x}" y1="23" x2="${x}" y2="${h-25}" class="plot-grid"/>`+tx(x,h-3,`${t*25}%`,'s-axis','text-anchor="middle"');
      }
      keys.forEach((key,i)=>{
        const value=row(key,source)[metric],y=top+i*step;
        body+=tx(x0-22,y+14,labels[key],'s-label','text-anchor="end"');
        body+=rect(x0,y-10,(value||0)*cw,bh,colors[key],5,`class="grow-bar" style="--order:${i}"`)+tx(x0+(value||0)*cw+15,y+bh/2,p(value),'s-value');
      });
      return frame(body,`${metricInfo[metric]} · ${sources[source]}`,1200,h);
    }
    function resultFooter(source,extra='') {return note(`${sources[source]} · seed 0 · test subset · ${extra||'cùng đầu vào DAS'}`);}
    function comparison(keys,metric,source){return controls(keySource(source),keyMetrics(metric))+bars(keys,metric,source)+resultFooter(source);}
    function curve(key,selected){
      const rows=data.methods[key].rounds,best=rows.reduce((a,b)=>a.val_score>=b.val_score?a:b),current=rows[Math.max(0,Math.min(29,selected-1))],left=85,top=42,bottom=303,pw=1030,ph=bottom-top;
      let body='';
      for(let i=0;i<=4;i++){const y=bottom-ph*i/4;body+=`<line x1="${left}" y1="${y}" x2="1115" y2="${y}" class="plot-grid"/>`+tx(left-17,y+6,`${i*25}%`,'s-axis','text-anchor="end"');}
      [1,5,10,15,20,25,30].forEach(r=>body+=tx(left+(r-1)/29*pw,bottom+32,r,'s-axis','text-anchor="middle"'));
      const bx=left+(best.round-1)/29*pw;
      body+=`<line x1="${bx}" y1="28" x2="${bx}" y2="${bottom}" stroke="${C.green}" stroke-width="2" stroke-dasharray="5 6"/>`+tx(Math.max(195,Math.min(980,bx)),20,`Best vòng ${best.round}: ${p(best.val_score)}`,'s-chart-note','text-anchor="middle"');
      [['val_f1mp_cicddos2019','CIC',C.blue],['val_f1mp_unsw_nb15','UNSW',C.coral],['val_score','Trung bình',C.green]].forEach(([metric,label,color])=>{
        const path=rows.map((r,i)=>`${i?'L':'M'}${left+(r.round-1)/29*pw},${bottom-r[metric]*ph}`).join(' ');
        body+=`<path d="${path}" fill="none" stroke="${color}" stroke-width="4" stroke-linejoin="round" class="draw-curve" pathLength="1"/>`;
        rows.forEach(r=>body+=`<circle cx="${left+(r.round-1)/29*pw}" cy="${bottom-r[metric]*ph}" r="5" fill="${color}" class="curve-point"><title>Vòng ${r.round} · ${label}: ${p(r[metric])}</title></circle>`);
        body+=circle(left+(current.round-1)/29*pw,bottom-current[metric]*ph,8,'white',`stroke="${color}" stroke-width="3"`);
      });
      return frame(body,`30 vòng validation ${labels[key]}`,1200,355)+`<div class="curve-readout"><label>Vòng <strong>${current.round}</strong><input type="range" min="1" max="30" value="${current.round}" data-control="round" aria-label="Vòng validation"></label><span style="--series:${C.blue}">CIC <b>${p(current.val_f1mp_cicddos2019)}</b></span><span style="--series:${C.coral}">UNSW <b>${p(current.val_f1mp_unsw_nb15)}</b></span><span style="--series:${C.green}">Trung bình <b>${p(current.val_score)}</b></span></div>`;
    }
    function confusion(state){
      const key=state.method||'prox',source=state.testSource||'cicddos2019',mode=state.matrixMode||'percent',m=data.methods[key],classes=data.classes;
      const cm=classes.map(a=>classes.map(b=>m.confusion.find(r=>r.dataset_id===source&&r.true===a&&r.pred===b).n));
      const short=['Bình thường','DoS/DDoS','Tấn công khác'],size=90,x0=230,y0=52;
      let body=tx(364,19,'NHÃN DỰ ĐOÁN','s-axis','text-anchor="middle"');
      short.forEach((s,i)=>{body+=tx(x0+i*size+43,40,s,'s-matrix-axis','text-anchor="middle"')+tx(x0-18,y0+i*size+47,s,'s-label','text-anchor="end"');});
      cm.forEach((r,i)=>{
        const total=r.reduce((a,b)=>a+b,0);
        r.forEach((v,j)=>{
          const share=total?v/total:null;
          body+=rect(x0+j*size,y0+i*size,size-5,size-5,total?`rgba(36,89,196,${.06+(share||0)*.63})`:'#eef1f5',9);
          body+=tx(x0+j*size+42,y0+i*size+48,total?(mode==='count'?n(v):n(share*100,1)+'%'):'N/A','s-matrix-value',`text-anchor="middle" style="fill:${C.ink}"`);
        });
      });
      body+=tx(745,47,'RECALL THEO LỚP','s-axis');
      m.per_class.filter(r=>r.dataset_id===source).forEach((r,i)=>{
        const y=96+i*92;body+=tx(745,y,short[i],'s-label')+tx(1115,y,p(r.recall),'s-value','text-anchor="end"')+rect(745,y+16,370,8,'#e6ebf2',4)+rect(745,y+16,(r.recall||0)*370,8,C.blue,4)+tx(745,y+50,`support ${n(r.support)}`,'s-caption');
      });
      return controls(select('method','Mô hình',Object.entries(labels),key),select('testSource','Nguồn test',data.sources.map(s=>[s,sources[s]]),source),select('matrixMode','Hiển thị',[['percent','Tỷ lệ theo hàng'],['count','Số mẫu']],mode))+frame(body,'Ma trận nhầm lẫn argmax và recall theo lớp',1200,350)+note('Hàng = nhãn thật. Lớp không có mẫu thật: N/A. FAR nhị phân dùng quy tắc xác suất riêng.');
    }

    function render(slide,state={}){
      const step=phase(state),source=state.source||'mean_over_sources',metric=state.metric||'f1_macro_present';
      switch(slide.view){
        case 'home':return home();
        case 'roadmap':return roadmap();
        case 'dataset-overview':{
          const ds=data.dataset_catalog,lm=data.label_map;
          const classColor={BENIGN:C.green,DOS_DDOS:C.blue,OTHER_ATTACK:C.purple};
          const cls=(src,name)=>data.classes.find(k=>lm[src][k].includes(name.toLowerCase()))||'OTHER_ATTACK';
          const norm=x=>{const y=x.replace(/^DrDoS_/,'');return ({Syn:'SYN','UDP-lag':'UDP-Lag',UDPLag:'UDP-Lag'})[y]||y;};
          const agg=entries=>{const m=new Map();entries.forEach(([k,v])=>m.set(k,(m.get(k)||0)+v));return [...m].sort((a,b)=>b[1]-a[1]);};
          const rows={cicddos2019:agg(Object.values(ds.cicddos2019.label_counts).flatMap(d=>Object.entries(d).map(([k,v])=>[norm(k),v]))),
            unsw_nb15:agg(ds.unsw_nb15.splits.flatMap(x=>Object.entries(x.labels)))};
          const days=ds.cicddos2019.days,perDay=days.map(d=>{const m={};Object.entries(ds.cicddos2019.label_counts[d.date]).forEach(([k,v])=>{m[norm(k)]=(m[norm(k)]||0)+v;});return m;});
          const dayHead=days.map(d=>`<span>${e(d.date.slice(0,5))}<small>${/test/i.test(d.role)?'test':'train/val'}</small></span>`).join('');
          const dayCells=name=>perDay.map((m,i)=>m[name]?`<i class="on" title="${e(days[i].date)}: ${n(m[name])} mẫu"></i>`:`<i class="off" title="${e(days[i].date)}: không có"></i>`).join('');
          const sub={cicddos2019:'UNB / CIC · 2 ngày thu thập',
            unsw_nb15:'UNSW Canberra · '+ds.unsw_nb15.splits.map(x=>`${e(x.name)} ${n(x.rows)}`).join(' · ')};
          const panel=src=>{const d=ds[src],r=rows[src],max=r[0][1],cic=src==='cicddos2019';
            return `<section class="lbl-panel" style="--accent:${cic?C.blue:C.coral}"><header><h3>${e(d.title)}</h3><span>${sub[src]}</span></header><div class="lbl-stats"><span><b>${n(d.local_rows)}</b> mẫu</span><span><b>${d.local_columns}</b> cột</span></div><div class="lbl-rows${cic?' with-days':''}">${cic?`<div class="lbl-row lbl-head"><span>Nhãn</span>${dayHead}<span></span><span>Tổng</span></div>`:''}${r.map(([name,v])=>`<div class="lbl-row"><span>${e(name)}</span>${cic?dayCells(name):''}<div><i style="width:max(3px,${v/max*100}%);background:${classColor[cls(src,name)]}"></i></div><b>${n(v)}</b></div>`).join('')}</div></section>`;};
          return `<div class="lbl-legend"><span>Nhãn gom về:</span>${data.classes.map(k=>`<span><i style="background:${classColor[k]}"></i>${k}</span>`).join('')}</div><div class="lbl-panels">${data.sources.map(panel).join('')}</div>`;
        }
        case 'schema':{
          const ds=data.dataset_catalog,c=x=>`<code>${e(x)}</code>`,u=x=>`<small>${e(x)}</small>`;
          const rows=[
            [c('duration_s')+u('giây'),c('Flow Duration')+u('µs ÷ 10⁶'),c('dur')+u('giây')],
            [c('fwd_packets / bwd_packets')+u('số gói hai chiều'),c('Total Fwd / Backward Packets'),c('spkts / dpkts')],
            [c('fwd_bytes / bwd_bytes')+u('số byte hai chiều'),c('Fwd / Bwd Packets Length Total'),c('sbytes / dbytes')],
            [c('fwd_iat_mean_s / bwd_iat_mean_s')+u('giây'),c('Fwd / Bwd IAT Mean')+u('µs ÷ 10⁶'),c('sinpkt / dinpkt')+u('ms ÷ 10³')],
            [c('protocol_group')+u('TCP · UDP · ICMP · OTHER'),c('Protocol')+u('số: 6, 17, 1…'),c('proto')+u('chuỗi: tcp, udp…')]];
          return `<div class="schema-center"><div class="compare-summary"><span>CIC <b>${ds.cicddos2019.local_columns} cột</b> → <b>8 trường</b></span><span>UNSW <b>${ds.unsw_nb15.local_columns} cột</b> → <b>8 trường</b></span></div>`+compareTable(['Sau · trường chung','Trước · CIC-DDoS2019','Trước · UNSW-NB15'],rows,0)+'</div>';
        }
        case 'label-map':{
          const ds=data.dataset_catalog,lm=data.label_map,col={BENIGN:C.green,DOS_DDOS:C.blue,OTHER_ATTACK:C.purple};
          const cicCounts={};Object.values(ds.cicddos2019.label_counts).forEach(d=>Object.entries(d).forEach(([k,v])=>{cicCounts[k]=(cicCounts[k]||0)+v;}));
          const unswCounts={};ds.unsw_nb15.splits.forEach(x=>Object.entries(x.labels).forEach(([k,v])=>{unswCounts[k]=(unswCounts[k]||0)+v;}));
          const pick=(counts,src,cls)=>Object.entries(counts).filter(([k])=>lm[src][cls].includes(k.toLowerCase().replace(/\s+/g,''))).sort((a,b)=>b[1]-a[1]);
          const chips=list=>list.length?`<div class="lm-chips">${list.map(([k])=>`<span>${e(k)}</span>`).join('')}</div>`:'<div class="lm-none">không có</div>';
          const sum=list=>list.reduce((a,[,v])=>a+v,0);
          const rows=data.classes.map(cls=>{const a=pick(cicCounts,'cicddos2019',cls),b=pick(unswCounts,'unsw_nb15',cls);
            return `<div class="lm-row" style="--c:${col[cls]}">${chips(a)}<b class="lm-arrow">→</b><div class="lm-class"><strong>${cls}</strong><span>CIC ${n(sum(a))} · UNSW ${n(sum(b))}</span></div><b class="lm-arrow">←</b>${chips(b)}</div>`;}).join('');
          return `<div class="lm-wrap"><div class="lm-row lm-head"><span>Trước · nhãn gốc CIC-DDoS2019</span><span></span><span>Sau · lớp chung</span><span></span><span>Trước · nhãn gốc UNSW-NB15</span></div>${rows}</div>`;
        }
        case 'quality':{
          const act={drop:['Loại dòng','#c34d35'],miss:['Gán missing','#a07322'],keep:['Gom vào OTHER',C.blue],stop:['Dừng pipeline','#17263c']};
          const c=x=>`<code>${e(x)}</code>`,v=x=>`<span class="qa-val">${e(x)}</span>`;
          const rows=[
            [c('fwd_packets / bwd_packets'),v('−3')+v('rỗng')+v('∞'),'drop','Không xác định được flow'],
            [c('fwd_packets + bwd_packets'),v('0'),'drop','Flow rỗng, không có gói nào'],
            [c('duration_s'),v('−1')+v('rỗng')+v('∞'),'miss','Giữ dòng, bật cờ duration_missing; không đổi thành 0'],
            [c('fwd_bytes, bwd_bytes, IAT'),v('âm')+v('∞'),'miss','Một phép đo hỏng, các cột khác vẫn dùng được'],
            [c('fwd_iat_mean_s'),v('fwd_packets = 1'),'miss','Cần ít nhất 2 gói cùng chiều mới có khoảng cách'],
            [c('protocol'),v('47 (GRE)')+v('"sctp"'),'keep','Giao thức hiếm gom chung một nhóm'],
            [c('nhãn'),v('nhãn không có trong bảng'),'stop','Không tự đoán lớp; phải thêm quy tắc rồi chạy lại']
          ].map(([f,val,a,why])=>[f,val,`<span class="qa-act" style="--a:${act[a][1]}">${act[a][0]}</span>`,`<small class="qa-why">${e(why)}</small>`]);
          const outcomes=[['Hợp lệ','Giữ nguyên',C.green],['Một phép đo hỏng','Gán missing',act.miss[1]],['Flow không hợp lệ','Loại dòng',act.drop[1]],['Nhãn lạ','Dừng pipeline',act.stop[1]]];
          const overview=`<div class="qa-overview"><div class="qa-step"><b>Mỗi dòng sau khi chuẩn hóa</b><span>7 số đo · giao thức · nhãn</span></div><i>→</i><div class="qa-step"><b>Kiểm tra từng giá trị</b><span>âm, rỗng, vô hạn, không đủ gói, nhãn lạ</span></div><i>→</i><div class="qa-outs">${outcomes.map(([k,v,col])=>`<span style="--a:${col}"><em>${k}</em>${v}</span>`).join('')}</div></div>`;
          return `<div class="qa-wrap">${overview}${compareTable(['Trường','Giá trị gặp phải','Xử lý','Lý do'],rows)}</div>`;
        }
        case 'split':{
          let body=icon('data',40,125,88)+tx(85,250,'Mỗi nguồn','s-label','text-anchor="middle"')+edge('M145,165 L280,165',C.blue,true)+circle(310,165,11,C.blue);
          body+=edge('M325,155 C410,155 415,70 520,70',C.green,true)+rect(545,25,600,90,'#eaf5ef',16)+tx(570,63,'TEST GIỮ RIÊNG','s-scene-title')+tx(570,94,'CIC: ngày khác · UNSW: testing-set','s-label');
          body+=edge('M325,180 C405,180 410,220 510,220',C.blue,true)+tx(530,170,'POOL TRAIN → 5 FOLD THEO NHÓM','s-axis');
          for(let i=0;i<5;i++)body+=rect(530+i*123,190,105,102,i===0?'#fff0e8':'#eaf0fb',12)+tx(582+i*123,230,`Fold ${i+1}`,'s-label','text-anchor="middle"')+tx(582+i*123,268,i===0?'VAL':'TRAIN','s-axis','text-anchor="middle"');
          return frame(body,'Chia test trước và chia train validation theo nhóm',1200,310);
        }
        case 'sampling':{
          const pal={BENIGN:C.green,DOS_DDOS:C.blue,OTHER_ATTACK:C.purple},parts=[['train','Train'],['val','Validation'],['test','Test']];
          let body='',y=22;
          data.classes.forEach((k,j)=>body+=rect(330+j*230,y-12,16,16,pal[k],4)+tx(354+j*230,y+2,k,'s-label'));
          y+=30;
          data.sources.forEach((src,si)=>{
            body+=tx(40,y+20,si?'UNSW-NB15':'CIC-DDoS2019','s-scene-title');y+=36;
            parts.forEach(([key,name])=>{
              const counts=data.quality.used_counts[src][key],total=Object.values(counts).reduce((a,b)=>a+b,0);let x=330;
              body+=tx(300,y+25,`${name} · ${n(total)}`,'s-label','text-anchor="end"');
              data.classes.forEach(k=>{const v=counts[k]||0,w=v/total*830;if(!w)return;body+=rect(x,y,w-3,36,pal[k],5);if(w>95)body+=tx(x+w/2,y+25,n(v),'s-bar-value','text-anchor="middle"');x+=w;});
              y+=46;
            });
            y+=10;
          });
          return frame(body,'Số mẫu theo lớp trong từng tập của mỗi nguồn',1200,y+4);
        }
        case 'clients':{
          // Gộp "lấy subset" và "chia client": subset theo nguồn → cơ chế chia → bằng chứng hai client bằng nhau.
          const split=data.quality.client_split||{},counts=split.counts_by_original_label||{},used=data.quality.used_counts;
          const pal={BENIGN:C.green,DOS_DDOS:C.blue,OTHER_ATTACK:C.purple},short={BENIGN:'BENIGN',DOS_DDOS:'DoS/DDoS',OTHER_ATTACK:'OTHER_ATTACK'};
          const total=o=>Object.values(o||{}).reduce((s,v)=>s+v,0),src0=used[data.sources[0]];
          const legend=`<div class="cs-legend">${data.classes.map(k=>`<span><i style="background:${pal[k]}"></i>${short[k]}</span>`).join('')}</div>`;
          const strip=`<div class="cs-strip">
              <div class="cs-step"><b>Subset mỗi nguồn</b><span>${n(total(src0.train))} train · ${n(total(src0.val))} val · ${n(total(src0.test))} test · không nhân bản</span></div><em>→</em>
              <div class="cs-step"><b>Trong từng nhãn gốc</b><span>xáo bằng seed ${e(split.seed??'')}, chia lần lượt</span><span class="cs-seq">${[0,1,0,1,0,1].map(k=>`<i class="${k?'b':'a'}">${k+1}</i>`).join('')}<small>…</small></span></div><em>→</em>
              <div class="cs-step"><b>2 client / nguồn</b><span>Test không chia, giữ theo nguồn</span></div></div>`;
          const block=(src,si)=>{
            const cs=data.clients.filter(c=>c.dataset_id===src),[a,b]=cs.map(c=>counts[`client_${c.client}`]||{});
            const bars=[['train','Train'],['val','Val'],['test','Test']].map(([k,name])=>{const cnt=used[src][k]||{},t=total(cnt);
              return `<div class="cs-bar"><span>${name} · ${n(t)}</span><div>${data.classes.filter(c=>cnt[c]>0).map(c=>{const p=cnt[c]/t*100;return `<i style="flex:${cnt[c]};background:${pal[c]}" title="${short[c]}: ${n(cnt[c])}">${p>=7?Math.round(p)+'%':''}</i>`;}).join('')}</div></div>`;}).join('');
            const missing=data.classes.filter(c=>!(used[src].train[c]>0)),present=data.classes.filter(c=>used[src].train[c]>0);
            const rare=present.reduce((m,c)=>used[src].train[c]<used[src].train[m]?c:m,present[0]);
            const note=missing.length?`Không có lớp ${missing.map(c=>short[c]).join(', ')}`:`${short[rare]} ít nhất: ${n(used[src].train[rare])} mẫu train thật, giữ toàn bộ`;
            const labels=Object.entries(a.train||{}).sort((x,y)=>y[1]-x[1]);
            const maxDiff=Math.max(0,...['train','val'].flatMap(sp=>Object.keys({...a[sp],...b[sp]}).map(l=>Math.abs((a[sp]?.[l]||0)-(b[sp]?.[l]||0)))));
            const ex=[labels[0],labels.at(-1)].filter(Boolean).map(([l,v])=>`<span><em>${e(l)}</em>${n(v)} · ${n(b.train?.[l]||0)}</span>`).join('');
            return `<section class="cs-block" style="--accent:${si?C.coral:C.blue}"><header><h3>${si?'UNSW-NB15':'CIC-DDoS2019'}</h3></header>
              <div class="cs-bars">${bars}</div><p class="cs-note">${e(note)}</p>
              <div class="cs-clients">${cs.map((c,k)=>`<div class="cs-client ${k?'b':'a'}"><strong>Client ${c.client}</strong><span>${n(c.n_train)} train · ${n(c.n_val)} val</span></div>`).join('')}</div>
              <div class="cs-proof"><b>${labels.length} nhãn gốc · lệch tối đa ${maxDiff} mẫu/nhãn</b>${ex}</div></section>`;
          };
          const purpose=`<div class="cs-purpose"><b>Mục đích</b><span>Hai client cùng nguồn có <strong>cùng phân bố nhãn</strong> (lệch ≤ 1 mẫu mỗi nhãn) và nhận <strong>các dòng rời nhau</strong>: không dòng nào thuộc cả hai client. Khác biệt thật nằm giữa CIC và UNSW.</span></div>`;
          return `<div class="cs-merged">${strip}${legend}<div class="cs-wrap">${data.sources.map(block).join('')}</div>${purpose}</div>`;
        }
        case 'feature-map':{
          const c=x=>`<code>${e(x)}</code>`;
          const base=['duration_s','fwd_packets','bwd_packets','fwd_bytes','bwd_bytes','fwd_iat_mean_s','bwd_iat_mean_s'];
          const groups=[
            ['Tổng hai chiều',[['total_packets','fwd + bwd packets'],['total_bytes','fwd + bwd bytes']]],
            ['Tốc độ · chia duration',[['flow_packets_s','total_packets / s'],['fwd_packets_s','fwd_packets / s'],['bwd_packets_s','bwd_packets / s'],['flow_bytes_s','total_bytes / s']]],
            ['Tỷ lệ chiều về',[['bwd_packet_fraction','bwd / total packets'],['bwd_byte_fraction','bwd / total bytes']]],
            ['Kích thước gói TB',[['fwd_packet_size_mean','fwd_bytes / fwd_packets'],['bwd_packet_size_mean','bwd_bytes / bwd_packets']]]];
          const fixed=[['proto_tcp','one-hot giao thức'],['proto_udp',''],['proto_icmp',''],['proto_other',''],['duration_missing','cờ: duration thiếu'],['duration_zero','cờ: duration = 0']];
          const colA=`<section class="fm-col"><header><b>8</b>Trường cơ sở</header><div class="fm-list">${base.map(x=>`<div class="fm-item keep">${c(x)}<span>giữ nguyên</span></div>`).join('')}<div class="fm-item proto">${c('protocol_group')}<span>→ one-hot</span></div></div></section>`;
          const colB=`<section class="fm-col mid"><header><b>10</b>Đặc trưng tạo thêm</header>${groups.map(([g,items])=>`<div class="fm-group"><small>${g}</small>${items.map(([k,f])=>`<div class="fm-item new">${c(k)}<span>${e(f)}</span></div>`).join('')}</div>`).join('')}</section>`;
          const colC=`<section class="fm-col fix"><header><b>6</b>Cột cố định (0/1)</header><div class="fm-list">${fixed.map(([k,f])=>`<div class="fm-item fixed">${c(k)}${f?`<span>${e(f)}</span>`:''}</div>`).join('')}</div></section>`;
          const total=`<div class="fm-total"><span><b>7</b> giữ nguyên</span><i>+</i><span><b>10</b> tạo thêm</span><i>=</i><span class="k"><b>17</b> liên tục</span><i>+</i><span class="f"><b>6</b> cố định</span><i>=</i><span class="all"><b>23</b> đầu vào ALL</span></div>`;
          return `<div class="fm-wrap"><div class="fm-grid">${colA}<b class="fm-arrow">→</b>${colB}<b class="fm-arrow">+</b>${colC}</div>${total}</div>`;
        }
        case 'logarithm':{
          let body='';
          [data.histogram.raw,data.histogram.log].forEach((hist,j)=>{
            const x0=70+j*610,base=270,max=Math.max(...hist.counts),pw=490;
            body+=tx(x0+245,30,j?'Sau log1p':'Trước log1p','s-scene-title','text-anchor="middle"');
            [0,.5,1].forEach(t=>body+=`<line x1="${x0}" y1="${base-t*190}" x2="${x0+pw}" y2="${base-t*190}" class="plot-grid"/>`+tx(x0-10,base-t*190+5,n(t*max/hist.n*100)+'%','s-axis','text-anchor="end"'));
            hist.counts.forEach((val,i)=>body+=rect(x0+i*pw/20,base-val/max*190,pw/20-3,val/max*190,j?C.blue:C.gray,3,`class="grow-up" style="--order:${i*.12}"`));
            body+=tx(x0,302,'0','s-axis')+tx(x0+pw,302,n(hist.max,j?2:0),'s-axis','text-anchor="end"')+tx(x0+245,338,j?'ln(1 + giây)':'giây','s-label','text-anchor="middle"');
          });
          const formula=`<div class="nz-formula"><b>x′ = ln(1 + x)</b><span>Áp cho <strong>cả 17 cột liên tục</strong></span><span>x âm hoặc ∞ → missing</span><span>6 cột 0/1 giữ nguyên</span></div>`;
          return formula+`<p class="nz-caption">Ví dụ trên cột <code>duration_s</code> · ${n(data.histogram.raw.n)} mẫu train</p>`+frame(body,'Phân bố duration_s trước và sau log1p');
        }
        case 'afn':{
          // Ví dụ thật từ tham số AFN đã lưu: cùng một giá trị total_packets, z khác nhau theo giao thức.
          const afn=data.afn,col='total_packets',ci=afn.columns.indexOf(col),raw=25,lx=Math.log1p(raw);
          const par=g=>({mu:afn.groups[g].mean[ci],sd:afn.groups[g].scale[ci]});
          const row=(g,name,cls)=>{const {mu,sd}=par(g),z=(lx-mu)/sd;
            return `<div class="nz-row ${cls}"><b>${name}</b><span>μ = ${n(mu,2)} <small>(≈ ${n(Math.expm1(mu),0)} gói)</small></span><span>σ = ${n(sd,2)}</span><strong>z = ${z>=0.005?'+':''}${n(z,2)}</strong></div>`;};
          const steps=[['1','Tách train theo giao thức','Mỗi flow thuộc một nhóm TCP / UDP / ICMP / OTHER'],
            ['2','Tính μ, σ cho từng cột trong từng nhóm','Mỗi client gửi n, Σx, Σx²; server cộng lại từ 4 client, không gửi dòng dữ liệu'],
            ['3','z = (x′ − μ<sub>nhóm</sub>) / σ<sub>nhóm</sub>','z = 0: bằng mức trung bình của giao thức đó']];
          const left=`<div class="nz-steps">${steps.map(([k,t,d])=>`<div class="nz-step"><i>${k}</i><div><b>${t}</b><span>${d}</span></div></div>`).join('')}</div>`;
          const right=`<div class="nz-example"><header>Vì sao theo giao thức? Ví dụ thật</header>
            <p>Một flow có <code>${col}</code> = ${raw} gói → x′ = ln(1 + ${raw}) = ${n(lx,2)}</p>
            ${row('tcp','Nếu là TCP','tcp')}${row('udp','Nếu là UDP','udp')}${row('__all__','Nếu không tách giao thức','all')}
            <p class="nz-take">TCP thường nhiều gói hơn UDP, nên 25 gói là <b>bình thường với TCP</b> nhưng <b>cao với UDP</b>. Không tách giao thức thì hai mức này bị trộn.</p></div>`;
          // Mức điển hình (exp(μ) − 1, quy về đơn vị gốc) của từng giao thức trên train: lý do phải tách nhóm.
          const big=v=>v>=1e6?n(v/1e6,1)+' tr':v>=1e3?n(v/1e3,1)+' nghìn':n(v,v<10?2:0);
          const typ=(g,c)=>Math.expm1(afn.groups[g].mean[afn.columns.indexOf(c)]);
          const metrics=[['total_packets','gói / flow',v=>n(v,0)],['duration_s','giây / flow',v=>n(v,2)],['flow_bytes_s','byte / giây',big]];
          const protos=[['tcp','TCP'],['udp','UDP'],['other','OTHER'],['icmp','ICMP']].filter(([g])=>afn.groups[g]);
          const table=`<div class="nz-protos"><header>Mỗi giao thức có mức "bình thường" riêng <small>· μ của từng nhóm trên train, quy về đơn vị gốc · ICMP chỉ ${n(afn.groups.icmp?.n_rows||0)} dòng nên không đọc</small></header>
            <div class="nz-pgrid" style="--cols:${protos.length}"><span></span>${protos.map(([g,name])=>`<b>${name}<small>${n(afn.groups[g].n_rows)} dòng</small></b>`).join('')}
            ${metrics.map(([c,unit,f])=>`<span>${unit}</span>${protos.map(([g])=>`<em>${afn.groups[g].n_rows<100?'—':f(typ(g,c))}</em>`).join('')}`).join('')}</div></div>`;
          return `<div class="nz-grid">${left}${right}</div>${table}<div class="nz-rules"><span class="train-lock">μ, σ chỉ học từ train</span><span>Validation / test áp lại, không học lại</span><span>σ ≈ 0 → dùng 1</span><span>Nhóm không có mẫu → dùng μ, σ chung</span><span>Missing → z = 0</span></div>`;
        }
        case 'das':{
          const d=data.das_config,f=x=>n(x,x<0.01?3:1);
          return `<div class="th-wrap"><div class="th-grid">
            <section class="th-card"><header><b>1</b><span>CRA <em>(Conditional Relevance Assessor)</em><small>Đánh giá mức liên quan với nhãn</small></span></header>
              <div class="th-formula">relevance(x) = <sup>1</sup>⁄<sub>|C|</sub> · Σ<sub>c</sub> ρ(x, 1[y = c])²</div>
              <div class="th-formula sm">ρ(a, b) = Cov(a, b) / √(Var a · Var b)</div>
              <ul><li><code>1[y = c]</code> = 1 nếu flow thuộc lớp c, ngược lại 0</li><li>Trung bình trên các lớp có mặt: BENIGN, DOS_DDOS, OTHER_ATTACK</li><li>Điểm càng cao → đặc trưng càng giúp phân biệt các lớp</li></ul></section>
            <section class="th-card"><header><b>2</b><span>IDF <em>(Iterative Dependency Filter)</em><small>Lọc lặp các cột phụ thuộc nhau</small></span></header>
              <ol class="th-steps"><li>Sắp 17 cột theo relevance giảm dần</li><li>Bỏ nếu relevance ≤ θ = <b>${f(d.theta)}</b> (gần như không liên quan)</li><li>Bỏ nếu |ρ| ≥ γ = <b>${f(d.gamma)}</b> với một cột đã giữ (trùng thông tin)</li><li>Giữ tối đa K = <b>${d.max_continuous}</b> cột</li></ol></section></div>
            <div class="th-flow"><span>17 cột liên tục<small>train · sau log1p + AFN · gộp 4 client</small></span><i>→</i><span class="a">CRA<small>xếp hạng</small></span><i>→</i><span class="a">IDF<small>lọc theo thứ tự</small></span><i>→</i><span class="k">12 cột giữ<small>+ 6 cột cố định không qua DAS</small></span></div></div>`;
        }
        case 'ranking':{
          const rows=data.feature_ranking,max=Math.max(...rows.map(r=>r.relevance_pooled));
          const kind=r=>r.status==='selected'?['keep','Giữ']:String(r.reason).startsWith('redundant_with')?['red',`Trùng với ${String(r.reason).split(':')[1].split('(')[0]} · |ρ| = ${n(Number(String(r.reason).split('|r|=')[1].replace(')','')),3)}`]:['low','Relevance ≤ θ'];
          return `<div class="rk-wrap"><div class="rk-legend"><span class="keep">Giữ</span><span class="red">Loại · trùng thông tin</span><span class="low">Loại · ít liên quan</span></div><div class="rk-rows">${rows.map(r=>{const [k,t]=kind(r);return `<div class="rk-row ${k}"><em>${r.rank}</em><code>${e(r.feature)}</code><div><i style="width:max(3px,${r.relevance_pooled/max*100}%)"></i></div><b>${n(r.relevance_pooled,4)}</b><span>${e(t)}</span></div>`;}).join('')}</div></div>`;
        }
        case 'das-corr':{
          const {features,corr}=data.das_corr,N=features.length,cs=34,L=250,T=34,rk=Object.fromEntries(data.feature_ranking.map(r=>[r.feature,r]));
          const pairs=data.feature_ranking.filter(r=>String(r.reason).startsWith('redundant_with')).map(r=>[r.feature,String(r.reason).split(':')[1].split('(')[0]]);
          const hit=new Set(pairs.flatMap(([a,b])=>[`${a}|${b}`,`${b}|${a}`]));
          let body='';
          features.forEach((f,i)=>{const col=rk[f].status==='selected'?'#17263c':'#c34d35';
            body+=`<text x="${L-10}" y="${T+i*cs+cs*0.66}" text-anchor="end" class="hm-label" style="fill:${col}">${e(f)} <tspan class="hm-rank">${i+1}</tspan></text>`;
            body+=`<text x="${L+i*cs+cs/2}" y="${T-10}" text-anchor="middle" class="hm-label hm-rank" style="fill:${col}">${i+1}</text>`;});
          features.forEach((a,i)=>features.forEach((b,j)=>{const v=Math.abs(corr[i][j]),fill=i===j?'#e9edf3':`rgba(36,89,196,${(0.04+0.96*v).toFixed(3)})`;
            body+=`<rect x="${L+j*cs}" y="${T+i*cs}" width="${cs-1}" height="${cs-1}" fill="${fill}"><title>${e(a)} · ${e(b)}: |ρ| = ${n(v,3)}</title></rect>`;
            if(hit.has(`${a}|${b}`))body+=`<rect x="${L+j*cs+1}" y="${T+i*cs+1}" width="${cs-3}" height="${cs-3}" fill="none" stroke="#c34d35" stroke-width="3"/>`;}));
          const W=L+N*cs+6,H=T+N*cs+6;
          const side=pairs.map(([a,b])=>{const v=Math.abs(corr[features.indexOf(a)][features.indexOf(b)]);return `<div class="hm-pair"><b>${n(v,3)}</b><span><code>${e(a)}</code> trùng <code>${e(b)}</code></span><small>→ loại ${e(a)}</small></div>`;}).join('');
          const scale=`<div class="hm-scale"><span>|ρ| = 0</span><i></i><span>1</span></div>`;
          return `<div class="hm-wrap"><div class="hm-plot"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Ma trận tương quan 17 đặc trưng liên tục"><title>Ma trận tương quan |ρ| 17 đặc trưng liên tục</title>${body}</svg></div><aside class="hm-side"><h3>Cặp có |ρ| ≥ ${n(data.das_config.gamma,1)}</h3>${side}<p>Số = thứ hạng CRA. Chữ đỏ: cột bị loại. Ô viền đỏ: cặp trùng thông tin.</p>${scale}</aside></div>`;
        }
        case 'feature-sets':{
          const keep=data.feature_ranking.filter(r=>r.status==='selected').map(r=>r.feature),drop=data.feature_ranking.filter(r=>r.status!=='selected');
          const fixed=['proto_tcp','proto_udp','proto_icmp','proto_other','duration_missing','duration_zero'];
          const chips=(xs,cls)=>`<div class="fs-chips ${cls}">${xs.map(x=>`<code>${e(x)}</code>`).join('')}</div>`;
          const why=r=>String(r.reason).startsWith('redundant_with')?`trùng ${String(r.reason).split(':')[1].split('(')[0]}`:'ít liên quan';
          return `<div class="fs-wrap"><section class="fs-in"><header><b>${keep.length+fixed.length}</b><span>đầu vào DAS · đưa vào huấn luyện</span></header><small>${keep.length} cột liên tục được giữ</small>${chips(keep,'keep')}<small>${fixed.length} cột cố định</small>${chips(fixed,'fix')}</section>
            <section class="fs-out"><header><b>${drop.length}</b><span>cột bị loại</span></header>${drop.map(r=>`<div class="fs-drop"><code>${e(r.feature)}</code><span>${why(r)}</span></div>`).join('')}</section></div>
            <div class="fs-total"><span>ALL <b>23</b></span><i>−</i><span><b>${drop.length}</b> bị loại</span><i>=</i><span class="k">DAS <b>${keep.length+fixed.length}</b></span><em>Cùng split, cùng mẫu; ALL được giữ làm đối chứng ở giai đoạn 8</em></div>`;
        }
        case 'architecture':{
          let body='';
          const xs=[60,310,565,820,1080],titles=['Vector flow','Linear → 8×8','ResNet + VGG','Swin','3 logits'];
          body+=lines(xs[0],155,['f₁','f₂','⋮','fF'],'s-field',31,'text-anchor="middle"');
          body+=grid(xs[1]-53,95,8,8,10,3,C.blue,'class="tensor-grid"');
          for(let i=3;i>=0;i--)body+=rect(xs[2]-58+i*12,95-i*10,100,110,i%2?'#c1d0e9':'#e1e9f6',8,'stroke="#7e9cc4"');
          body+=grid(xs[3]-57,92,4,4,24,5,C.coral,'class="tensor-grid"');
          [0,1,2].forEach(i=>body+=circle(xs[4],104+i*50,14,[C.blue,C.coral,C.purple][i]));
          xs.forEach((x,i)=>{body+=tx(x,265,titles[i],'s-label','text-anchor="middle"');if(i<4)body+=edge(`M${x+82},150L${xs[i+1]-82},150`,C.blue,true)+pulse(`M${x+82},150L${xs[i+1]-82},150`,C.blue,-i*.7);});
          body+=tx(600,333,'Lưới được học từ vector; không phải ảnh đầu vào','s-emphasis','text-anchor="middle"');
          return frame(body,'Kiến trúc ResVGG-SwinNet với luồng biểu diễn chuyển động');
        }
        case 'forward':{
          const featureSet=state.featureSet||'das',F=featureSet==='das'?18:23;
          const shapes=[`B × ${F}`,'B × 1 × 8 × 8','B × 32 × 8 × 8','B × 64 × 8 × 8','B × 64 token × 64','B × 3'];
          const names=['Vector','Linear','ResNet','VGG','Swin','Head'],i=step%6;
          let body=tx(600,61,names[i],'s-scene-title','text-anchor="middle"')+tx(600,130,shapes[i],'s-number','text-anchor="middle"');
          if(i===0){for(let k=0;k<F;k++)body+=rect(260+k*29,185,18,56,k<12?C.blue:C.purple,4,'class="grow-up"');}
          else if(i===5){[C.blue,C.coral,C.purple].forEach((c,k)=>body+=circle(450+k*150,235,34,c)+tx(450+k*150,298,`logit ${k}`,'s-label','text-anchor="middle"'));}
          else if(i===4)body+=grid(340,180,16,4,23,6,C.coral,'class="tensor-grid"');
          else for(let k=(i===1?0:3);k>=0;k--)body+=grid(520+k*12,170-k*10,8,8,12,3,k%2?C.purple:C.blue,'class="tensor-grid"');
          return controls(select('featureSet','Đầu vào',[['das','DAS · 18'],['all','ALL · 23']],featureSet))+phases(names,step)+frame(body,'Minh họa hình dạng tensor qua từng khối')+note('B là batch size. Hình minh họa kích thước; không phải activation đo được. Softmax tính trong loss / dự đoán.');
        }
        case 'methods':{
          let body='';
          ['Local-only','Centralized','Federated'].forEach((s,i)=>body+=tx(200+i*400,33,s,'s-scene-title','text-anchor="middle"'));
          [[80,C.blue],[160,C.blue],[240,C.coral],[320,C.coral]].forEach(([x,col])=>body+=icon('server',x-22,163,44,col)+icon('train',x-16,85,32,C.gray)+edge(`M${x},160L${x},125`,C.gray,true));
          body+=icon('data',470,168,60,C.coral)+icon('data',650,168,60,C.coral)+icon('server',555,68,70,C.purple)+edge('M505,167L570,130',C.coral,true)+edge('M680,167L625,130',C.coral,true);
          body+=icon('train',967,68,66,C.green);
          [[850,C.blue],[935,C.blue],[1065,C.coral],[1150,C.coral]].forEach(([x,col],k)=>{const d=`M${x},170L${k<2?985:1015},138`;body+=icon('server',x-22,175,44,col)+edge(d,col,true)+pulse(d,col,-k*.5);});
          body+=lines(200,296,['Bốn mô hình riêng','Mỗi client tự học'],'s-label',31,'text-anchor="middle"')+lines(600,296,['Gửi dữ liệu train','Một nơi huấn luyện'],'s-label',31,'text-anchor="middle"')+lines(1000,296,['Gửi cập nhật mô hình','Phối hợp học chung'],'s-label',31,'text-anchor="middle"');
          return frame(body,'So sánh trực quan ba cách tổ chức học')+note('FL không tự bảo đảm riêng tư tuyệt đối. Chất lượng dự đoán được kiểm chứng bằng thí nghiệm.');
        }
        case 'round':{
          const s=Number(state.step||0)%4,steps=['Gửi mô hình','Học tại client','Gửi cập nhật','Tổng hợp'],y=157;
          const cx=[[110,80],[260,230],[1090,80],[940,230]];let body=circle(600,y,78,'#e9f0fd')+icon('train',558,y-44,85,C.green);
          cx.forEach(([x,yy],i)=>body+=icon('server',x-34,yy-34,68,i<2?C.blue:C.coral)+tx(x,yy+52,`Client ${i+1}`,'s-axis','text-anchor="middle"'));
          body+=tx(185,335,'CIC · mỗi client n = 50.000','s-label','text-anchor="middle"')+tx(1015,335,'UNSW · mỗi client n = 50.000','s-label','text-anchor="middle"')+tx(600,291,steps[s],'s-scene-title','text-anchor="middle"');
          if(s===0||s===2){const ends=[[150,95],[300,215],[1050,95],[900,215]],hub=[[525,135],[530,185],[675,135],[670,185]];ends.forEach(([x,yy],i)=>{const [hx,hy]=hub[i],d=s===0?`M${hx},${hy}L${x},${yy}`:`M${x},${yy}L${hx},${hy}`;body+=edge(d,i<2?C.blue:C.coral,true)+pulse(d,i<2?C.blue:C.coral,-i*.5);});}
          if(s===1){cx.forEach(([x,yy],i)=>body+=circle(x,yy,50,'none',`stroke="${i<2?'#2459c4':'#c34d35'}" stroke-width="3" stroke-dasharray="10 8" class="spin-ring"`));}
          if(s===3)body+=tx(600,48,'w mới = 0,25 (w₁ + w₂ + w₃ + w₄)','s-formula','text-anchor="middle"');
          return `<div class="phase-controls">${steps.map((t,i)=>`<button data-action="step" data-value="${i}" aria-pressed="${s===i}"><span>${i+1}</span>${t}</button>`).join('')}</div><span class="round-step-label">BƯỚC ${s+1} / 4</span>`+frame(body,'Một vòng FedAvg tương tác')+`<div class="criteria-strip"><span><b>30</b> vòng</span><span><b>5</b> epoch / vòng</span><span>Adam · lr <b>0,001</b></span><span>batch <b>64</b> · dropout <b>0,3</b></span></div>`+(()=>{
            // Class weight trong loss (khác trọng số tổng hợp 25%): nghịch đảo tần suất lớp tại client, lớp vắng = 0.
            const cw=data.class_weights||{},short={BENIGN:'BENIGN',DOS_DDOS:'DoS/DDoS',OTHER_ATTACK:'OTHER'};
            const one=src=>{const c=data.clients.find(x=>x.dataset_id===src),w=cw[`client_${c.client}`]||[];
              return `<div><b>${src==='cicddos2019'?'CIC · client 1, 2':'UNSW · client 3, 4'}</b>${data.classes.map((k,i)=>`<span>${short[k]} <strong>${w[i]?n(w[i],2):'—'}</strong></span>`).join('')}</div>`;};
            return `<div class="cw-strip"><header>Class weight trong loss <small>lớp càng ít mẫu, trọng số càng cao · giới hạn [0,1; 10] · lớp vắng = 0</small></header>${data.sources.map(one).join('')}</div>`;})();
        }
        case 'experiments':{
          let body='';
          [['Local × 4','DAS','150 epoch / client',C.gray],['Centralized','DAS','150 epoch',C.purple],['FedAvg','ALL / DAS','30 × 5 epoch',C.blue],['FedProx','DAS · μ = 0,1','30 × 5 epoch',C.green]].forEach(([name,input,budget,color],i)=>{
            const y=38+i*73;body+=circle(75,y+10,7,color)+tx(110,y+18,name,'s-scene-title')+tx(390,y+18,input,'s-label')+edge(`M600,${y+10}L770,${y+10}`,color,true)+tx(820,y+18,budget,'s-label');
          });
          return frame(body,'Ma trận phương pháp, đầu vào và ngân sách',1200,310)+`<div class="checkpoint-route"><span>Train: học trọng số</span><b>→</b><strong>Validation: chọn best</strong><b>→</b><span>Test: chấm mô hình đã chốt</span></div>`+note('Seed 0. Best FL / centralized theo F1-macro-present trung bình theo nguồn trên validation; local theo validation của chính client.');
        }
        case 'metrics':{
          let body='';
          [['Ba lớp','argmax P(c)','F1-macro-present'],['Mọi tấn công','1 − P(BENIGN) ≥ 0,5','Attack-F1 · FAR'],['DoS/DDoS','P(DOS_DDOS) ≥ 0,5','DoS-F1 · FAR']].forEach(([name,rule,score],i)=>{
            const x=200+i*400;body+=circle(x,96,60,['#edf3fc','#fff0e9','#eff2fb'][i])+icon(['select','shield','results'][i],x-29,67,58,[C.blue,C.coral,C.purple][i])+tx(x,199,name,'s-scene-title','text-anchor="middle"')+tx(x,247,rule,'s-field','text-anchor="middle"')+tx(x,299,score,'s-label','text-anchor="middle"');
          });
          return frame(body,'Ba nhiệm vụ đánh giá với quy tắc quyết định khác nhau',1200,340)+`<div class="evidence-line"><strong>Mean = (metric CIC + metric UNSW) / 2</strong><span>Pooled tính lại từ dự đoán gộp</span></div>`+note('Macro-present: CIC có 2 lớp thật, UNSW có 3. FAR lấy mẫu số là BENIGN.');
        }
        case 'baseline':return comparison([...LOCALS,'das','central'],metric,source);
        case 'transfer':{
          const keys=[...LOCALS,'das','central'];let body=tx(527,29,'TEST CIC','s-axis','text-anchor="middle"')+tx(842,29,'TEST UNSW','s-axis','text-anchor="middle"');
          keys.forEach((key,i)=>{
            const y=50+i*54;body+=tx(360,y+31,labels[key],'s-label','text-anchor="end"');
            data.sources.forEach((s,j)=>{const value=row(key,s)[metric],x=390+j*315;body+=rect(x,y,275,46,`rgba(36,89,196,${.06+(value||0)*.53})`,8)+tx(x+137,y+32,p(value),'s-value','text-anchor="middle"');});
          });
          return controls(keyMetrics(metric))+frame(body,'Ma trận đánh giá xuyên nguồn theo mô hình',1200,385)+note('Một mô hình local có thể tốt trên nguồn riêng nhưng giảm mạnh khi chuyển miền.');
        }
        case 'all-das':{
          let body='';const x0=280,pw=740;
          [0,.25,.5,.75,1].forEach(t=>{const x=x0+t*pw;body+=`<line x1="${x}" y1="40" x2="${x}" y2="300" class="plot-grid"/>`+tx(x,329,n(t*100)+'%','s-axis','text-anchor="middle"');});
          ['cicddos2019','unsw_nb15','mean_over_sources'].forEach((s,i)=>{
            const y=86+i*87,a=row('all',s)[metric],b=row('das',s)[metric],delta=(b-a)*100;
            body+=tx(250,y+8,['CIC','UNSW','Trung bình'][i],'s-label','text-anchor="end"')+`<line x1="${x0+a*pw}" y1="${y}" x2="${x0+b*pw}" y2="${y}" stroke="${C.blue}" stroke-width="5" class="draw-curve" pathLength="1"/>`+circle(x0+a*pw,y,10,C.gray)+circle(x0+b*pw,y,12,C.blue)+tx(x0+a*pw,y-20,p(a),'s-axis','text-anchor="middle"')+tx(x0+b*pw,y+35,p(b),'s-value','text-anchor="middle"')+tx(1100,y+8,(delta>0?'+':'')+n(delta,2),'s-label','text-anchor="middle"');
          });
          return controls(keyMetrics(metric))+`<div class="chart-legend"><span style="--series:${C.gray}">ALL · 23 đầu vào</span><span style="--series:${C.blue}">DAS · 18 đầu vào</span><span>Chênh lệch: điểm phần trăm</span></div>`+frame(body,'Biểu đồ dumbbell ALL so với DAS')+note(`Cùng mẫu và ngân sách. Best ALL vòng ${row('all').selected_round}; best DAS vòng ${row('das').selected_round}, chọn riêng bằng validation.`);
        }
        case 'das-tradeoff':{
          let body='';
          [['f1_macro_present','F1-macro'],['dos_f1','F1 DoS/DDoS'],['attack_far_benign','FAR mọi tấn công ↓']].forEach(([key,name],i)=>{
            const a=row('all',source)[key],b=row('das',source)[key],delta=(b-a)*100,x=200+i*400;
            body+=tx(x,37,name,'s-scene-title','text-anchor="middle"')+tx(x,115,p(a),'s-number s-gray','text-anchor="middle"')+tx(x,163,'ALL → DAS','s-axis','text-anchor="middle"')+tx(x,231,p(b),'s-number s-blue','text-anchor="middle"')+tx(x,298,(delta>0?'+':'')+n(delta,2)+' điểm %','s-label','text-anchor="middle"');
          });
          return controls(keySource(source))+frame(body,'Ba mặt đánh đổi của lựa chọn đặc trưng')+note('F1 cao hơn là tốt; FAR thấp hơn là tốt. DAS không cải thiện đồng thời mọi mục tiêu.');
        }
        case 'heterogeneity':{
          const key=state.curve||'das';return controls(select('curve','Lịch sử validation',[['das',labels.das],['all',labels.all],['prox',labels.prox]],key))+curve(key,Number(state.round||1))+note('Đủ 30 vòng. Khác biệt miền là một giả thuyết giải thích; không khẳng định duy nhất nguyên nhân.');
        }
        case 'prox-mechanism':{
          let body=tx(600,38,'L(w) = L_local(w) + μ/2 · ‖w − w_global‖²','s-formula','text-anchor="middle"');
          body+=circle(600,205,111,'#edf6f1','stroke="#8ab7a0" stroke-dasharray="7 8" stroke-width="2"')+circle(600,205,10,C.green)+tx(600,249,'w_global','s-label','text-anchor="middle"');
          ['M600,205L272,104','M600,205L930,105'].forEach(d=>body+=edge(d,C.gray,true));
          ['M600,205L536,145','M600,205L674,150'].forEach(d=>body+=edge(d,C.blue,true)+pulse(d,C.blue));
          body+=lines(210,154,['Client A','hướng cục bộ'],'s-label',30,'text-anchor="middle"')+lines(1000,154,['Client B','hướng cục bộ'],'s-label',30,'text-anchor="middle"')+tx(600,351,'Neo cập nhật gần mô hình đầu vòng · μ = 0,1','s-emphasis','text-anchor="middle"');
          return frame(body,'Minh họa trực giác số hạng proximal, không phải quỹ đạo đo')+note('Minh họa cơ chế. Server vẫn FedAvg; số hạng proximal không phải bộ lọc chống đầu độc.');
        }
        case 'prox-results':return comparison(['das','central','prox'],metric,source)+`<div class="result-observation"><strong>${p(row('prox',source)[metric])}</strong><span>${metricInfo[metric]} · FedProx</span><b>${n((row('prox',source)[metric]-row('das',source)[metric])*100,2)} điểm phần trăm so với FedAvg</b></div>`;
        case 'errors':return confusion(state);
        case 'contributions':{
          let body='';
          const keys=['das','all','prox','central'],vals=keys.map(k=>row(k).f1_macro_present),xs=[150,450,750,1050];
          for(let i=0;i<2;i++)body+=edge(`M${xs[i]+40},${270-vals[i]*230}L${xs[i+1]-40},${270-vals[i+1]*230}`,C.blue,true);
          body+=`<line x1="${xs[2]+40}" y1="${270-vals[2]*230}" x2="${xs[3]-40}" y2="${270-vals[3]*230}" stroke="${C.purple}" stroke-width="3" stroke-dasharray="7 7"/>`;
          keys.forEach((k,i)=>body+=circle(xs[i],270-vals[i]*230,24,k==='prox'?C.green:k==='central'?C.purple:C.blue)+tx(xs[i],210-vals[i]*230,p(vals[i]),'s-number','text-anchor="middle"')+tx(xs[i],300,labels[k],'s-scene-title','text-anchor="middle"'));
          return frame(body,'F1-macro trung bình của ba cấu hình FL và mốc centralized',1200,345)+`<div class="contribution-caption"><span><b>Dữ liệu</b>Pipeline hai nguồn, bốn client, có truy vết</span><span><b>Đối chứng</b>Kiểm tra từng lựa chọn</span><span><b>Kết quả</b>FedProx tốt nhất trong FL, còn sau centralized và đổi lấy FAR</span></div>`+note('F1-macro-present trung bình hai nguồn · seed 0. Centralized là mốc tham chiếu (nét đứt), không phải cận trên được bảo đảm.');
        }
        case 'limits':{
          let body='';
          [['Nhiều seed','Kiểm tra độ lặp lại','train'],['Chọn ngưỡng','Giảm FAR trên validation','select'],['Test độc lập','Rà overlap, thêm nguồn','shield']].forEach(([title,sub,kind],i)=>{
            const x=180+i*420;body+=circle(x,120,68,'#edf3fc')+icon(kind,x-31,89,62)+tx(x,235,title,'s-scene-title','text-anchor="middle"')+tx(x,280,sub,'s-label','text-anchor="middle"');
            if(i<2)body+=edge(`M${x+90},120L${x+330},120`,C.blue,true)+pulse(`M${x+90},120L${x+330},120`,C.blue,-i);
          });
          return frame(body,'Ba ưu tiên tiếp theo từ giới hạn thực nghiệm')+`<div class="end-links"><a href="#pipeline">← Quay về pipeline</a>${byId.has('appendix-formulas')?'<a href="#appendix-formulas">Phụ lục & trao đổi →</a>':''}</div>`;
        }
        default:return null;
      }
    }
    return {home,roadmap,render};
  }
  const api={create};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.DeckVisuals=api;
})(typeof globalThis!=='undefined'?globalThis:this);
