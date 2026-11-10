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
  const labels={all:'FedAvg · ALL',das:'FedAvg · DAS',prox:'FedProx · DAS',central:'Centralized',local_cic:'Local · CIC',local_unsw:'Local · UNSW'};
  const colors={all:'#607187',das:C.blue,prox:C.green,central:C.purple,local_cic:C.coral,local_unsw:'#a07322'};
  const keyMetrics=value=>select('metric','Chỉ số',Object.entries(metricInfo),value);
  const keySource=value=>select('source','Tập đánh giá',Object.entries(sources).filter(([k])=>!['worst_source','pooled_predictions'].includes(k)),value);

  function create(ctx){
    const {data,content,groups,byId,row,assets={}}=ctx;
    const phase=state=>Number(state.phase||0);
    const stat=(value,label,detail='')=>`<div class="editorial-stat"><strong>${e(value)}</strong><span>${e(label)}</span>${detail?`<small>${e(detail)}</small>`:''}</div>`;
    function home(){
      const positions=[[80,50],[340,50],[600,50],[860,50],[1120,50],[1120,210],[773,210],[427,210],[80,210]];
      const names=[['Tổng quan','dữ liệu'],['Làm sạch','& đồng nhất'],['Phân chia','dữ liệu'],['Xây dựng','đặc trưng'],['Chuẩn hóa','dữ liệu'],['Lựa chọn','đặc trưng'],['Kiến trúc','& huấn luyện'],['Đánh giá','kết quả'],['Kết luận','& hướng đi']];
      let body='';
      for(let i=0;i<8;i++){
        const [x,y]=positions[i],[nx,ny]=positions[i+1];
        const d=i===4?`M${x},${y+40} C${x+80},${y+70} ${nx+80},${ny-70} ${nx},${ny-40}`:i<4?`M${x+48},${y} L${nx-48},${ny}`:`M${x-48},${y} L${nx+48},${ny}`;
        body+=edge(d,'#b6c8e0',true)+pulse(d,i<5?C.blue:C.coral,-i*.7);
      }
      groups.forEach(g=>{
        const i=content.stages.findIndex(s=>s.id===g.id),[x,y]=positions[i],kind=['data','clean','split','features','normalize','select','train','results','conclusion'][i];
        body+=`<a href="#${g.slides[0].id}" class="pipeline-stop" style="--order:${i}" aria-label="${e(g.title)}">${circle(x,y,39,i===7?'#e2efff':'#f1f5fb','class="stop-disc"')}${icon(kind,x-22,y-22,44,i===7?C.coral:C.blue)}${tx(x-54,y-35,String(i+1).padStart(2,'0'),'s-stage-index')}${lines(x,y+63,names[i],'s-pipeline-title',24,'text-anchor="middle"')}</a>`;
      });
      return `<section class="cover"><div class="cover-copy"><p class="eyebrow">ĐỒ ÁN AN TOÀN THÔNG TIN</p><h1>Học liên kết.<br><em>Phát hiện tấn công mạng.</em></h1><p>Hai nguồn dữ liệu. Một mô hình chung.<br>Từ phép đo lưu lượng đến bằng chứng thực nghiệm.</p><div class="cover-facts"><span>CIC-DDoS2019</span><b>+</b><span>UNSW-NB15</span><i>2 client / 3 lớp</i></div></div><div class="cover-art">${assets.network?`<img src="${assets.network}" alt="Minh họa hai mạng cục bộ trao đổi cập nhật với mô hình toàn cục" width="1672" height="941">`:''}<svg viewBox="0 0 800 380" aria-hidden="true"><path d="M120 260Q400 80 680 260"/><circle r="6"><animateMotion dur="4s" repeatCount="indefinite" path="M120 260Q400 80 680 260"/></circle><circle r="5"><animateMotion dur="4s" begin="-2s" repeatCount="indefinite" path="M680 260Q400 80 120 260"/></circle></svg><span class="art-caption">MINH HỌA HỌC LIÊN KẾT</span></div></section><section class="pipeline-map"><div class="pipeline-heading"><span>QUY TRÌNH THỰC HIỆN</span><span>Chọn một giai đoạn để bắt đầu ↘</span></div>${frame(body,'Pipeline chín giai đoạn có đường truyền dữ liệu chuyển động',1200,300)}</section><div class="cover-bottom"><span>ResVGG-SwinNet · FedAvg · DAS · FedProx</span><a href="#${groups[0]?.slides[0].id||'pipeline'}">Bắt đầu trình bày →</a></div>`;
    }

    function bars(keys,metric,source){
      const x0=285,cw=755,top=47,step=73,h=top+keys.length*step+20;
      let body='';
      for(let t=0;t<=4;t++){
        const x=x0+t*cw/4;body+=`<line x1="${x}" y1="23" x2="${x}" y2="${h-25}" class="plot-grid"/>`+tx(x,h-3,`${t*25}%`,'s-axis','text-anchor="middle"');
      }
      keys.forEach((key,i)=>{
        const value=row(key,source)[metric],y=top+i*step;
        body+=tx(x0-22,y+14,labels[key],'s-label','text-anchor="end"');
        body+=rect(x0,y-10,(value||0)*cw,37,colors[key],5,`class="grow-bar" style="--order:${i}"`)+tx(x0+(value||0)*cw+15,y+18,p(value),'s-value');
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
      [['val_f1mp_pid0','CIC',C.blue],['val_f1mp_pid1','UNSW',C.coral],['val_score','Trung bình',C.green]].forEach(([metric,label,color])=>{
        const path=rows.map((r,i)=>`${i?'L':'M'}${left+(r.round-1)/29*pw},${bottom-r[metric]*ph}`).join(' ');
        body+=`<path d="${path}" fill="none" stroke="${color}" stroke-width="4" stroke-linejoin="round" class="draw-curve" pathLength="1"/>`;
        rows.forEach(r=>body+=`<circle cx="${left+(r.round-1)/29*pw}" cy="${bottom-r[metric]*ph}" r="5" fill="${color}" class="curve-point"><title>Vòng ${r.round} · ${label}: ${p(r[metric])}</title></circle>`);
        body+=circle(left+(current.round-1)/29*pw,bottom-current[metric]*ph,8,'white',`stroke="${color}" stroke-width="3"`);
      });
      return frame(body,`30 vòng validation ${labels[key]}`,1200,355)+`<div class="curve-readout"><label>Vòng <strong>${current.round}</strong><input type="range" min="1" max="30" value="${current.round}" data-control="round" aria-label="Vòng validation"></label><span style="--series:${C.blue}">CIC <b>${p(current.val_f1mp_pid0)}</b></span><span style="--series:${C.coral}">UNSW <b>${p(current.val_f1mp_pid1)}</b></span><span style="--series:${C.green}">Trung bình <b>${p(current.val_score)}</b></span></div>`;
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
        case 'dataset-overview':{
          const ds=data.dataset_catalog;
          return `<div class="dataset-spread">${data.sources.map((s,i)=>`<section><div class="dataset-emblem">${frame(icon(i?'shield':'data',10,8,90,i?C.coral:C.blue),ds[s].title,110,110)}</div><p class="eyebrow">${i?'UNSW CANBERRA':'UNB · CANADIAN INSTITUTE FOR CYBERSECURITY'}</p><h2>${ds[s].title}</h2><p class="dataset-one-line">${i?'Chín nhóm xâm nhập và lưu lượng bình thường.':'Lưu lượng bình thường và các kịch bản DDoS.'}</p><div class="dataset-big">${n(ds[s].local_rows)} <span>mẫu</span></div><div class="dataset-counts"><span><b>${ds[s].local_columns}</b> cột</span><span><b>${ds[s].local_measurements}</b> đặc trưng</span><span><b>${ds[s].local_files}</b> file ${i?'CSV':'Parquet'}</span></div><p class="dataset-version">${i?'Training 175.341 · Testing 82.332':'Hai ngày: 12/01 và 11/03/2019'}</p></section>`).join('')}</div><div class="evidence-line"><span>TEST TRONG BÀI</span><strong>50.000 CIC + 50.000 UNSW = 100.000 flow</strong></div><p class="figure-caption">Số liệu bản đang dùng. Benchmark UNSW đầy đủ: 2.540.044 mẫu, 49 trường; CIC gốc mô tả hơn 80 đặc trưng.</p>`;
        }
        case 'cic-profile':{
          const d=data.dataset_catalog.cicddos2019;
          return `<div class="capture-origin"><span>Testbed mạng</span><b>→</b><span>25 người dùng mô phỏng</span><b>→</b><span>PCAP</span><b>→</b><strong>CICFlowMeter-V3</strong></div><div class="day-timeline">${d.days.map((day,i)=>`<section><div class="day-date"><span>NGÀY ${i+1}</span><h2>${day.date}</h2><b>${n(day.rows)} mẫu</b></div><p>${day.role} · ${day.files} file</p>${chips(day.local_attacks)}<small>+ BENIGN${i===0?' · Bản gốc còn mô tả SSDP, bản đang dùng không có SSDP.':''}</small></section>`).join('')}</div><div class="evidence-line"><strong>431.371 flow</strong><span>77 đặc trưng + Label = 78 cột</span><span>Thời lượng · gói/byte · IAT · cờ TCP</span></div>`;
        }
        case 'unsw-profile':{
          const d=data.dataset_catalog.unsw_nb15;
          return `<div class="capture-origin"><span>IXIA PerfectStorm</span><b>→</b><strong>100 GB PCAP</strong><b>→</b><span>Argus / Bro-IDS</span></div><div class="unsw-spread"><section><p class="eyebrow">9 NHÓM TẤN CÔNG + NORMAL</p><div class="attack-family-grid">${d.attacks.map((s,i)=>`<div><span>${String(i+1).padStart(2,'0')}</span>${s}</div>`).join('')}</div></section><section class="raw-partitions">${d.splits.map(s=>`<div><span>${s.name}</span><strong>${n(s.rows)}</strong><p>${s.role}</p></div>`).join('')}<p><b>45 cột</b> = 42 đặc trưng + id + attack_cat + label</p></section></div><div class="evidence-line"><span>BENCHMARK ĐẦY ĐỦ</span><strong>2.540.044 mẫu · 49 trường</strong><span>Giao thức · dịch vụ · gói/byte · TTL · IAT · jitter</span></div>`;
        }
        case 'schema':{
          const groupsMap=[{name:'Thời lượng',left:['Flow Duration'],mid:['duration_s'],right:['dur']},{name:'Gói & byte',left:['Total Fwd Packets','Total Backward Packets','Fwd Packets Length Total','Bwd Packets Length Total'],mid:['fwd_packets','bwd_packets','fwd_bytes','bwd_bytes'],right:['spkts','dpkts','sbytes','dbytes']},{name:'IAT hai chiều',left:['Fwd IAT Mean','Bwd IAT Mean'],mid:['fwd_iat_mean_s','bwd_iat_mean_s'],right:['sinpkt','dinpkt']},{name:'Giao thức',left:['Protocol'],mid:['protocol_group'],right:['proto']}],g=groupsMap[step%4];
          const start=g.mid.length===4?90:g.mid.length===2?135:165;
          let body=tx(190,38,'CIC-DDoS2019','s-scene-title','text-anchor="middle"')+tx(600,38,'SCHEMA CHUNG','s-scene-title','text-anchor="middle"')+tx(1010,38,'UNSW-NB15','s-scene-title','text-anchor="middle"');
          g.mid.forEach((s,i)=>{
            const y=start+i*60;
            body+=rect(20,y-30,340,58,'#f3f6fb',10)+tx(190,y+6,g.left[i],'s-field','text-anchor="middle"');
            body+=rect(440,y-30,320,58,'#e6eefc',10)+tx(600,y+6,s,'s-field canonical-field','text-anchor="middle"');
            body+=rect(840,y-30,340,58,'#fff1eb',10)+tx(1010,y+6,g.right[i],'s-field','text-anchor="middle"');
            const a=`M365,${y} L432,${y}`,b=`M835,${y} L768,${y}`;
            body+=edge(a,C.blue,true)+edge(b,C.coral,true)+pulse(a,C.blue,-i*.7)+pulse(b,C.coral,-i*.7);
          });
          body+=tx(600,332,'Cùng ý nghĩa → cùng trường → cùng mô hình','s-emphasis','text-anchor="middle"');
          return phases(groupsMap.map(s=>s.name),step)+frame(body,'Ánh xạ schema theo từng nhóm trường')+note('8 trường chung: 1 thời lượng + 4 gói/byte + 2 IAT + 1 giao thức. Metadata giữ riêng để truy vết.');
        }
        case 'units':{
          const topics=['Thời lượng','Khoảng cách gói','Giao thức','Nhãn'],i=step%4;
          const examples=[['CIC · micro giây','2.000.000 µs','÷ 1.000.000','2 s','UNSW dur đã tính bằng giây'],['UNSW · mili giây','2.000 ms','÷ 1.000','2 s','CIC IAT dùng µs nên chia 1.000.000'],['CIC / UNSW','6 / tcp','Gom cùng nhóm','TCP','UDP, ICMP và OTHER xử lý tương tự'],['CIC / UNSW','Benign / Normal','Ánh xạ tường minh','BENIGN','Các loại tấn công được gom bằng bảng nhãn']][i];
          return phases(topics,step)+frame(icon(i<2?'clock':i===2?'data':'select',45,92,135)+tx(285,91,examples[0],'s-label')+tx(285,169,examples[1],'s-number')+edge('M650,150 L810,150',C.blue,true)+tx(730,119,examples[2],'s-axis','text-anchor="middle"')+tx(930,170,examples[3],'s-number s-blue','text-anchor="middle"')+tx(600,290,examples[4],'s-emphasis','text-anchor="middle"'),'Ví dụ chuyển đơn vị và biểu diễn')+note('Ví dụ số minh họa. Chuyển đơn vị không phải chuẩn hóa thống kê z-score.');
        }
        case 'quality':{
          const y=150;
          let body=icon('data',18,115,80)+edge('M110,150 L240,150',C.blue,true)+rect(260,55,300,220,'#f0f5fd',22)+icon('clean',370,83,65)+lines(410,188,['Kiểm tra giá trị','và nhãn dữ liệu'],'s-scene-title',32,'text-anchor="middle"');
          [['Hợp lệ','Giữ lại',C.green,70],['Thiếu phép đo','Đánh dấu missing',C.blue,170],['Số gói không hợp lệ','Loại dòng',C.coral,270]].forEach(([title,sub,color,ty],i)=>{
            const d=`M565,150 C670,150 650,${ty} 785,${ty}`;
            body+=edge(d,color,true)+pulse(d,color,-i)+circle(815,ty,10,color)+tx(850,ty-3,title,'s-label')+tx(850,ty+26,sub,'s-caption');
          });
          return frame(body,'Minh họa quy tắc kiểm tra chất lượng')+`<div class="evidence-line"><span>BÁO CÁO HIỆN TẠI</span><strong>0 dòng bị loại · 0 nhãn lỗi</strong><span>Nhãn lạ/mâu thuẫn → dừng pipeline</span></div>`;
        }
        case 'clients':{
          let body='';
          data.clients.forEach((c,i)=>{
            const x=i?890:230,color=i?C.coral:C.blue;
            body+=circle(x,155,120,i?'#fff1eb':'#edf3fc','class="client-halo"')+icon('server',x-45,103,90,color)+tx(x,34,`CLIENT ${i+1}`,'s-axis','text-anchor="middle"')+tx(x,234,i?'UNSW-NB15':'CIC-DDoS2019','s-scene-title','text-anchor="middle"');
            body+=lines(x,295,[`Train ${n(c.n_train)}`,`Validation ${n(c.n_val)} · Test ${n(c.n_test)}`],'s-label',30,'text-anchor="middle"');
          });
          body+=icon('train',520,92,85,C.green)+tx(563,222,'Mô hình chung','s-label','text-anchor="middle"');
          ['M362,145L503,145','M756,145L625,145'].forEach((d,i)=>body+=edge(d,i?C.coral:C.blue,true)+pulse(d,i?C.coral:C.blue,-i));
          return frame(body,'Hai client giữ dữ liệu riêng theo nguồn')+note('Chia theo nguồn, không trộn ngẫu nhiên. Đây là tổ chức logic của mô phỏng.');
        }
        case 'split':{
          let body=icon('data',40,125,88)+tx(85,250,'Mỗi nguồn','s-label','text-anchor="middle"')+edge('M145,165 L280,165',C.blue,true)+circle(310,165,11,C.blue);
          body+=edge('M325,155 C410,155 415,70 520,70',C.green,true)+rect(545,25,600,90,'#eaf5ef',16)+tx(570,63,'TEST GIỮ RIÊNG','s-scene-title')+tx(570,94,'CIC: ngày khác · UNSW: testing-set','s-label');
          body+=edge('M325,180 C405,180 410,220 510,220',C.blue,true)+tx(530,170,'POOL TRAIN → 5 FOLD THEO NHÓM','s-axis');
          for(let i=0;i<5;i++)body+=rect(530+i*123,190,105,102,i===0?'#fff0e8':'#eaf0fb',12)+tx(582+i*123,230,`Fold ${i+1}`,'s-label','text-anchor="middle"')+tx(582+i*123,268,i===0?'VAL':'TRAIN','s-axis','text-anchor="middle"');
          body+=tx(600,341,'Cùng fingerprint → cùng một phía train hoặc validation','s-emphasis','text-anchor="middle"');
          return frame(body,'Chia test trước và chia train validation theo nhóm')+note('Chia tập → lấy subset → mới fit chuẩn hóa và DAS. Không khẳng định mọi vector train/test đều khác nhau.');
        }
        case 'sampling':{
          const partition=state.partition||'train';let body='';
          const palette=[C.blue,C.coral,C.purple];
          data.sources.forEach((s,i)=>{
            const counts=data.quality.used_counts[s][partition],total=Object.values(counts).reduce((a,b)=>a+b,0),y=73+i*158;let x=240;
            body+=tx(210,y+32,i?'UNSW':'CIC','s-scene-title','text-anchor="end"');
            data.classes.forEach((cls,j)=>{const val=counts[cls]||0,w=val/total*870;if(w)body+=rect(x,y,w-2,54,palette[j],5);x+=w;});
            data.classes.forEach((cls,j)=>body+=circle(260+j*290,y+92,5,palette[j])+tx(277+j*290,y+100,`${['BENIGN','DoS/DDoS','OTHER'][j]}: ${n(counts[cls]||0)}`,'s-label'));
          });
          return controls(select('partition','Subset',[['train','Train · 100.000 / nguồn'],['val','Validation · 20.000 / nguồn'],['test','Test · 50.000 / nguồn']],partition))+frame(body,'Phân bố nhãn thực tế trong từng subset',1200,345)+note('UNSW train DoS: 9.811 mẫu thật, không nhân bản để đạt sàn 10.000.');
        }
        case 'feature-map':{
          const xs=[145,445,745,1045];
          let body='';
          [['8','Trường cơ sở','data'],['17','Đặc trưng liên tục','features'],['6','Cột cố định','normalize'],['23','Đầu vào ALL','train']].forEach(([val,label,kind],i)=>{
            const x=xs[i];body+=icon(kind,x-35,50,70,i===3?C.green:C.blue)+tx(x,199,val,'s-giant','text-anchor="middle"')+tx(x,245,label,'s-label','text-anchor="middle"');
            if(i<3)body+=tx(x+150,190,i===1?'+':i===2?'=':'→','s-operator','text-anchor="middle"');
          });
          body+=lines(600,312,['Tốc độ = số lượng / thời gian · tỷ lệ = một chiều / tổng','Cột cố định: 4 giao thức + 2 cờ duration'],'s-emphasis',30,'text-anchor="middle"');
          return frame(body,'Tạo các nhóm đặc trưng từ tám trường cơ sở');
        }
        case 'feature-example':{
          const mode=state.example||'normal',duration=mode==='zero'?0:2,bwd=mode==='no-bwd'?0:2,bytes=bwd?400:0;
          let body=icon('server',40,60,85)+icon('server',1065,60,85,C.coral)+tx(85,182,'Nguồn','s-label','text-anchor="middle"')+tx(1108,182,'Đích','s-label','text-anchor="middle"');
          for(let i=0;i<8;i++)body+=rect(260+i*75,64,35,23,C.blue,5,`class="packet-forward" style="--order:${i}"`);
          for(let i=0;i<bwd;i++)body+=rect(490+i*110,116,35,23,C.coral,5,'class="packet-backward"');
          body+=tx(600,42,`8 gói / 800 byte →   ← ${bwd} gói / ${bytes} byte`,'s-scene-title','text-anchor="middle"')+tx(600,185,`Thời lượng: ${duration} giây`,'s-label','text-anchor="middle"');
          [['Tổng gói',n(8+bwd)],['Gói / giây',duration?n((8+bwd)/duration,1):'missing'],['Byte / giây',duration?n((800+bytes)/duration):'missing'],['Byte / gói về',bwd?'200':'missing']].forEach(([label,val],i)=>body+=tx(155+i*295,267,val,'s-number','text-anchor="middle"')+tx(155+i*295,309,label,'s-label','text-anchor="middle"'));
          return controls(select('example','Ví dụ giả định',[['normal','Flow hợp lệ'],['zero','Duration = 0'],['no-bwd','Không có gói chiều về']],mode))+frame(body,'Ví dụ tạo đặc trưng từ flow giả định')+note('Minh họa phép tính, không phải số liệu đo. Mẫu số không hợp lệ → missing; không tự gán rate = 0.');
        }
        case 'logarithm':{
          let body='';
          [data.histogram.raw,data.histogram.log].forEach((hist,j)=>{
            const x0=70+j*610,base=270,max=Math.max(...hist.counts),pw=490;
            body+=tx(x0+245,30,j?'Sau log1p':'Trước log1p','s-scene-title','text-anchor="middle"');
            [0,.5,1].forEach(t=>body+=`<line x1="${x0}" y1="${base-t*190}" x2="${x0+pw}" y2="${base-t*190}" class="plot-grid"/>`+tx(x0-10,base-t*190+5,n(t*max/hist.n*100)+'%','s-axis','text-anchor="end"'));
            hist.counts.forEach((val,i)=>body+=rect(x0+i*pw/20,base-val/max*190,pw/20-3,val/max*190,j?C.blue:C.gray,3,`class="grow-up" style="--order:${i*.12}"`));
            body+=tx(x0,302,'0','s-axis')+tx(x0+pw,302,n(hist.max,j?2:0),'s-axis','text-anchor="end"')+tx(x0+245,338,j?'ln(1 + giây)':'duration_s · giây','s-label','text-anchor="middle"');
          });
          return `<div class="math-ribbon"><span>0 → 0</span><span>999 → 6,91</span><span>999.999 → 13,82</span></div>`+frame(body,'Histogram duration thực tế trước và sau log1p')+note('200.000 mẫu train; tái dựng từ AFN đã lưu, có sai số float32. Hai trục x khác miền giá trị.');
        }
        case 'afn':{
          let body=icon('server',100,80,80)+icon('server',100,235,80,C.coral)+tx(205,120,'CIC · thống kê train','s-label')+tx(205,275,'UNSW · thống kê train','s-label');
          const a='M455,115C530,115 515,185 590,185',b='M455,270C530,270 515,185 590,185';
          body+=edge(a,C.blue,true)+edge(b,C.coral,true)+pulse(a,C.blue)+pulse(b,C.coral,-1.5)+circle(660,185,61,'#e8effc')+tx(660,197,'μ, σ','s-number','text-anchor="middle"')+edge('M735,185L860,185',C.blue,true)+tx(1005,170,'z = (x − μ) / σ','s-formula','text-anchor="middle"')+tx(1005,219,'Theo nhóm giao thức','s-label','text-anchor="middle"');
          body+=tx(600,36,'n hợp lệ · tổng · tổng bình phương','s-axis','text-anchor="middle"');
          return frame(body,'Gộp thống kê train để chuẩn hóa theo giao thức')+`<div class="evidence-line"><span class="train-lock">FIT: TRAIN</span><span>Validation / test chỉ transform</span><span>Missing → z = 0 · Có tham số dự phòng</span></div>`;
        }
        case 'das':{
          let body='';
          for(let i=0;i<17;i++)body+=rect(45+i*19,90,12,82,i<12?C.blue:C.gray,3,`class="grow-up" style="--order:${i*.15}"`);
          body+=tx(195,48,'17 cột liên tục','s-scene-title','text-anchor="middle"')+edge('M385,130L500,130',C.blue,true)+icon('select',535,70,110)+tx(590,218,'CRA + IDF','s-scene-title','text-anchor="middle"')+edge('M680,130L810,130',C.blue,true);
          for(let i=0;i<12;i++)body+=rect(845+i*22,90,14,82,C.blue,3,'class="grow-up"');
          body+=tx(970,48,'12 cột được giữ','s-scene-title','text-anchor="middle"');
          body+=edge('M180,230C180,300 950,300 970,230',C.purple,true)+tx(600,320,'6 cột cố định đi theo nhánh riêng','s-label','text-anchor="middle"');
          return frame(body,'Lọc đặc trưng liên tục, giữ sáu cột cố định')+`<div class="criteria-strip"><span>Relevance &gt; <b>0,001</b></span><span>|r| &lt; <b>0,9</b></span><span>Tối đa <b>12</b> cột liên tục</span></div>`;
        }
        case 'ranking':{
          const field='relevance_'+(state.rankingSource||'pooled'),list=data.feature_ranking.slice(0,6),max=Math.max(...list.map(r=>r[field])),x0=345,pw=650;
          let body='';
          list.forEach((r,i)=>{const y=38+i*46;body+=tx(x0-20,y+15,r.feature,'s-field','text-anchor="end"')+rect(x0,y-9,r[field]/max*pw,30,C.blue,4,`class="grow-bar" style="--order:${i}"`)+tx(x0+r[field]/max*pw+12,y+15,n(r[field],4),'s-label');});
          return controls(select('rankingSource','Relevance',[['pooled','Gộp train'],['cicddos2019','Riêng CIC'],['unsw_nb15','Riêng UNSW']],state.rankingSource||'pooled'))+frame(body,'Sáu đặc trưng đứng đầu theo thứ hạng pooled',1200,310)+`<div class="decision-examples"><span><b>total_bytes</b> bị loại: r = 0,977 với fwd_bytes</span><span><b>bwd_iat_mean_s</b> bị loại: relevance ≤ 0,001</span></div>`+note('Thứ hạng / quyết định theo pooled. Toàn bộ 17 cột và lý do loại nằm ở phụ lục.');
        }
        case 'feature-sets':{
          let body='';
          [['ALL',23,17,260,C.gray],['DAS',18,12,900,C.blue]].forEach(([label,total,cont,x,color])=>{
            body+=tx(x,45,label,'s-scene-title','text-anchor="middle"')+tx(x,152,total,'s-giant','text-anchor="middle"');
            for(let i=0;i<23;i++)body+=rect(x-175+i%12*29,190+Math.floor(i/12)*42,22,27,i>=total?'#eff1f4':i>=cont?C.purple:color,4,i>=total?'stroke="#cbd1dc" stroke-dasharray="3 3"':'class="grow-up"');
            body+=tx(x,310,`${cont} liên tục + 6 cố định`,'s-label','text-anchor="middle"');
          });
          body+=icon('select',548,125,85)+tx(590,255,'−5 cột','s-scene-title','text-anchor="middle"');
          return frame(body,'Đối chứng ALL 23 đầu vào và DAS 18 đầu vào')+note('Cùng mẫu, cùng split và ngân sách huấn luyện. Giảm cột không suy ra cùng tỷ lệ tiết kiệm tổng chi phí.');
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
          [[105,185],[295,185]].forEach(([x,y])=>body+=icon('server',x-28,y-28,56,C.gray)+icon('train',x-20,80,40,C.gray));
          body+=icon('data',470,168,60,C.coral)+icon('data',650,168,60,C.coral)+icon('server',555,68,70,C.purple)+edge('M505,167L570,130',C.coral,true)+edge('M680,167L625,130',C.coral,true);
          body+=icon('server',875,175,65)+icon('server',1060,175,65,C.coral)+icon('train',967,68,66,C.green);
          ['M920,175L985,135','M1080,175L1020,135'].forEach((d,i)=>body+=edge(d,i?C.coral:C.blue,true)+pulse(d,i?C.coral:C.blue,-i));
          body+=lines(200,296,['Hai mô hình riêng','Mỗi nguồn tự học'],'s-label',31,'text-anchor="middle"')+lines(600,296,['Gửi dữ liệu train','Một nơi huấn luyện'],'s-label',31,'text-anchor="middle"')+lines(1000,296,['Gửi cập nhật mô hình','Phối hợp học chung'],'s-label',31,'text-anchor="middle"');
          return frame(body,'So sánh trực quan ba cách tổ chức học')+note('FL không tự bảo đảm riêng tư tuyệt đối. Chất lượng dự đoán được kiểm chứng bằng thí nghiệm.');
        }
        case 'round':{
          const s=Number(state.step||0)%4,steps=['Gửi mô hình','Học tại client','Gửi cập nhật','Tổng hợp'],y=157;
          let body=circle(600,y,78,'#e9f0fd')+icon('train',558,y-44,85,C.green)+icon('server',115,y-45,92)+icon('server',990,y-45,92,C.coral);
          body+=tx(162,291,'CIC · n = 100.000','s-label','text-anchor="middle"')+tx(1036,291,'UNSW · n = 100.000','s-label','text-anchor="middle"')+tx(600,291,steps[s],'s-scene-title','text-anchor="middle"');
          if(s===0||s===2){const paths=s===0?['M510,157L240,157','M690,157L965,157']:['M240,157L510,157','M965,157L690,157'];paths.forEach((d,i)=>body+=edge(d,i?C.coral:C.blue,true)+pulse(d,i?C.coral:C.blue,-i));}
          if(s===1){body+=circle(162,y,80,'none','stroke="#2459c4" stroke-width="3" stroke-dasharray="10 8" class="spin-ring"')+circle(1036,y,80,'none','stroke="#c34d35" stroke-width="3" stroke-dasharray="10 8" class="spin-ring"');}
          if(s===3)body+=tx(600,48,'w mới = 0,5 w₁ + 0,5 w₂','s-formula','text-anchor="middle"');
          return `<div class="phase-controls">${steps.map((t,i)=>`<button data-action="step" data-value="${i}" aria-pressed="${s===i}"><span>${i+1}</span>${t}</button>`).join('')}</div><span class="round-step-label">BƯỚC ${s+1} / 4</span>`+frame(body,'Một vòng FedAvg tương tác')+`<div class="criteria-strip"><span><b>30</b> vòng</span><span><b>5</b> epoch / vòng</span><span>Adam · lr <b>0,001</b></span><span>batch <b>64</b> · dropout <b>0,3</b></span></div>`;
        }
        case 'experiments':{
          let body='';
          [['Local × 2','DAS','150 epoch',C.gray],['Centralized','DAS','150 epoch',C.purple],['FedAvg','ALL / DAS','30 × 5 epoch',C.blue],['FedProx','DAS · μ = 0,1','30 × 5 epoch',C.green]].forEach(([name,input,budget,color],i)=>{
            const y=38+i*73;body+=circle(75,y+10,7,color)+tx(110,y+18,name,'s-scene-title')+tx(390,y+18,input,'s-label')+edge(`M600,${y+10}L770,${y+10}`,color,true)+tx(820,y+18,budget,'s-label');
          });
          return frame(body,'Ma trận phương pháp, đầu vào và ngân sách',1200,310)+`<div class="checkpoint-route"><span>Train: học trọng số</span><b>→</b><strong>Validation: chọn best</strong><b>→</b><span>Test: chấm mô hình đã chốt</span></div>`+note('Seed 0. Best FL / centralized theo F1-macro-present trung bình hai validation; local theo validation nguồn riêng.');
        }
        case 'metrics':{
          let body='';
          [['Ba lớp','argmax P(c)','F1-macro-present'],['Mọi tấn công','1 − P(BENIGN) ≥ 0,5','Attack-F1 · FAR'],['DoS/DDoS','P(DOS_DDOS) ≥ 0,5','DoS-F1 · FAR']].forEach(([name,rule,score],i)=>{
            const x=200+i*400;body+=circle(x,96,60,['#edf3fc','#fff0e9','#eff2fb'][i])+icon(['select','shield','results'][i],x-29,67,58,[C.blue,C.coral,C.purple][i])+tx(x,199,name,'s-scene-title','text-anchor="middle"')+tx(x,247,rule,'s-field','text-anchor="middle"')+tx(x,299,score,'s-label','text-anchor="middle"');
          });
          return frame(body,'Ba nhiệm vụ đánh giá với quy tắc quyết định khác nhau',1200,340)+`<div class="evidence-line"><strong>Mean = (metric CIC + metric UNSW) / 2</strong><span>Pooled tính lại từ dự đoán gộp</span></div>`+note('Macro-present: CIC có 2 lớp thật, UNSW có 3. FAR lấy mẫu số là BENIGN.');
        }
        case 'baseline':return comparison(['local_cic','local_unsw','central','das'],metric,source);
        case 'transfer':{
          const keys=['local_cic','local_unsw','das','central'];let body=tx(550,29,'TEST CIC','s-axis','text-anchor="middle"')+tx(865,29,'TEST UNSW','s-axis','text-anchor="middle"');
          keys.forEach((key,i)=>{
            const y=60+i*72;body+=tx(310,y+37,labels[key],'s-label','text-anchor="end"');
            data.sources.forEach((s,j)=>{const value=row(key,s)[metric],x=390+j*315;body+=rect(x,y,275,60,`rgba(36,89,196,${.06+(value||0)*.53})`,8)+tx(x+137,y+39,p(value),'s-value','text-anchor="middle"');});
          });
          return controls(keyMetrics(metric))+frame(body,'Ma trận đánh giá xuyên nguồn theo mô hình',1200,365)+note('Một mô hình local có thể tốt trên nguồn riêng nhưng giảm mạnh khi chuyển miền.');
        }
        case 'all-das':{
          let body='';const x0=280,pw=740;
          [0,.25,.5,.75,1].forEach(t=>{const x=x0+t*pw;body+=`<line x1="${x}" y1="40" x2="${x}" y2="300" class="plot-grid"/>`+tx(x,329,n(t*100)+'%','s-axis','text-anchor="middle"');});
          ['cicddos2019','unsw_nb15','mean_over_sources'].forEach((s,i)=>{
            const y=86+i*87,a=row('all',s)[metric],b=row('das',s)[metric],delta=(b-a)*100;
            body+=tx(250,y+8,['CIC','UNSW','Trung bình'][i],'s-label','text-anchor="end"')+`<line x1="${x0+a*pw}" y1="${y}" x2="${x0+b*pw}" y2="${y}" stroke="${C.blue}" stroke-width="5" class="draw-curve" pathLength="1"/>`+circle(x0+a*pw,y,10,C.gray)+circle(x0+b*pw,y,12,C.blue)+tx(x0+a*pw,y-20,p(a),'s-axis','text-anchor="middle"')+tx(x0+b*pw,y+35,p(b),'s-value','text-anchor="middle"')+tx(1100,y+8,(delta>0?'+':'')+n(delta,2),'s-label','text-anchor="middle"');
          });
          return controls(keyMetrics(metric))+`<div class="chart-legend"><span style="--series:${C.gray}">ALL · 23 đầu vào</span><span style="--series:${C.blue}">DAS · 18 đầu vào</span><span>Chênh lệch: điểm phần trăm</span></div>`+frame(body,'Biểu đồ dumbbell ALL so với DAS')+note('Cùng mẫu và ngân sách. Best ALL vòng 24; best DAS vòng 4, chọn riêng bằng validation.');
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
          const vals=['all','das','prox'].map(k=>row(k).f1_macro_present),xs=[160,600,1040];
          for(let i=0;i<2;i++)body+=edge(`M${xs[i]+50},${270-vals[i]*230}L${xs[i+1]-50},${270-vals[i+1]*230}`,C.blue,true);
          ['all','das','prox'].forEach((k,i)=>body+=circle(xs[i],270-vals[i]*230,24,i===2?C.green:C.blue)+tx(xs[i],210-vals[i]*230,p(vals[i]),'s-number','text-anchor="middle"')+tx(xs[i],300,labels[k],'s-scene-title','text-anchor="middle"'));
          return frame(body,'Tiến trình F1-macro trung bình từ ALL đến FedProx',1200,345)+`<div class="contribution-caption"><span><b>Dữ liệu</b>Pipeline hai nguồn có truy vết</span><span><b>Đối chứng</b>Kiểm tra từng lựa chọn</span><span><b>Kết quả</b>Cải thiện F1, còn đánh đổi FAR</span></div>`+note('F1-macro-present trung bình hai nguồn · seed 0. Không suy ra ưu thế tổng quát.');
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
    return {home,render};
  }
  const api={create};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.DeckVisuals=api;
})(typeof globalThis!=='undefined'?globalThis:this);
