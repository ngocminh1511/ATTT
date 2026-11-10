(function (root) {
  'use strict';
  const COLORS = {all:'#607187',das:'#2459c4',prox:'#16704e',central:'#7254ad',local_cic:'#c34d35',local_unsw:'#a07322'};
  const Visuals=root.DeckVisuals||(typeof require==='function'?require('./visuals.js'):null);
  const LABELS = {all:'FedAvg · ALL',das:'FedAvg · DAS',prox:'FedProx · DAS',central:'Centralized · DAS',local_cic:'Local · CIC',local_unsw:'Local · UNSW'};
  const SOURCE_LABELS = {cicddos2019:'CIC-DDoS2019',unsw_nb15:'UNSW-NB15',mean_over_sources:'Trung bình đều hai nguồn',worst_source:'Kém nhất theo từng chỉ số',pooled_predictions:'Dự đoán gộp (pooled)'};
  const METRICS = {f1_macro_present:'F1-macro-present',dos_f1:'F1 DoS/DDoS',attack_f1:'F1 mọi tấn công',attack_recall:'Recall mọi tấn công',dos_recall:'Recall DoS/DDoS',attack_far_benign:'FAR mọi tấn công ↓',dos_far_benign:'FAR DoS/DDoS ↓',acc:'Accuracy',attack_roc_auc:'AUC mọi tấn công',dos_roc_auc:'AUC DoS/DDoS'};
  const CLASS_NAMES = ['BENIGN','DOS_DDOS','OTHER_ATTACK'];
  const CLASS_SHORT = ['BENIGN','DoS/DDoS','OTHER'];
  const CLASS_COLORS = ['#56d8e9','#f0b970','#b7a0f8'];
  const ORDER = ['local_cic','local_unsw','central','all','das','prox'];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = (value, digits=0) => value == null || !Number.isFinite(Number(value)) ? 'N/A' : Number(value).toLocaleString('vi-VN',{minimumFractionDigits:digits,maximumFractionDigits:digits});
  const pct = value => value == null ? 'N/A' : `${number(value * 100,2)}%`;
  const signed = value => `${value > 0 ? '+' : ''}${number(value,2)}`;
  const svg = (body, w=800, h=330, label='Sơ đồ minh họa') => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>${body}</svg>`;
  const text = (x,y,label,extra='') => `<text x="${x}" y="${y}" ${extra}>${esc(label)}</text>`;
  const panel = (body, cls='') => `<div class="panel ${cls}">${body}</div>`;
  const mini = (label,value,detail='') => `<div class="mini-stat"><span>${esc(label)}</span><strong>${esc(value)}</strong>${detail ? `<small>${esc(detail)}</small>` : ''}</div>`;
  const pill = (label,cls='') => `<span class="pill ${cls}">${esc(label)}</span>`;
  const formula = label => `<div class="formula">${esc(label)}</div>`;
  function table(headers,rows,cls='') {
    return `<div class="table-scroll ${cls}"><table><thead><tr>${headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((c,i)=>`<${i===0?'th scope="row"':'td'}>${c}</${i===0?'th':'td'}>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  function select(name,label,options,value) {
    return `<label class="select-control"><span>${esc(label)}</span><select data-control="${esc(name)}" aria-label="${esc(label)}">${options.map(([id,title])=>`<option value="${esc(id)}" ${String(value)===String(id)?'selected':''}>${esc(title)}</option>`).join('')}</select></label>`;
  }
  const controls = (...items) => `<div class="chart-controls">${items.join('')}</div>`;
  const legend = items => `<div class="legend">${items.map(([name,color])=>`<span><i style="background:${color}"></i>${esc(name)}</span>`).join('')}</div>`;
  function flow(items, label='Luồng xử lý') {
    const w=800,h=148,gap=25,bw=(w-gap*(items.length-1))/items.length;
    return svg(items.map((item,i)=>{
      const x=i*(bw+gap);
      return `<rect x="${x+1}" y="18" width="${bw-2}" height="104" rx="12" class="diagram-box"/>`+
        text(x+16,45,`${String(i+1).padStart(2,'0')}`, 'class="diagram-number"')+
        text(x+bw/2,74,item[0],'text-anchor="middle" class="diagram-title"')+
        text(x+bw/2,100,item[1]||'','text-anchor="middle" class="diagram-sub"')+
        (i<items.length-1?text(x+bw+gap/2,76,'→','text-anchor="middle" class="diagram-arrow"'):'');
    }).join(''),w,h,label);
  }
  function barChart(items,{label='So sánh',max=1}={}) {
    const left=176,right=81,top=32,row=48,w=800,h=top+items.length*row+40,cw=w-left-right;
    let body='';
    for(let i=0;i<=4;i++) {
      const x=left+i*cw/4;
      body+=`<line x1="${x}" y1="14" x2="${x}" y2="${h-28}" class="chart-grid"/>`+text(x,h-6,`${number(i*max*100/4,0)}%`,'text-anchor="middle" class="axis-label"');
    }
    items.forEach((r,i)=>{
      const y=top+i*row;
      body+=text(left-14,y+6,r.label,'text-anchor="end" class="bar-label"');
      if(r.value!=null) body+=`<rect x="${left}" y="${y-14}" width="${Math.max(0,r.value/max*cw)}" height="27" rx="5" fill="${r.color}"/>`;
      body+=text(left+(r.value==null?0:r.value/max*cw)+10,y+6,pct(r.value),'class="value-label"');
    });
    return svg(body,w,h,label);
  }
  function groupedChart(groups,series,label='So sánh ALL và DAS') {
    const w=800,h=330,left=60,bottom=266,cw=700,groupW=cw/groups.length,bw=47;
    let body='';
    for(let i=0;i<=4;i++) {
      const y=bottom-i*220/4;
      body+=`<line x1="${left}" y1="${y}" x2="${w-20}" y2="${y}" class="chart-grid"/>`+text(left-10,y+5,`${i*25}%`,'text-anchor="end" class="axis-label"');
    }
    groups.forEach((g,i)=>{
      const cx=left+groupW*(i+.5);
      series.forEach((s,j)=>{
        const v=g.values[j],x=cx+(j-(series.length-1)/2)*(bw+9)-bw/2;
        if(v!=null) body+=`<rect x="${x}" y="${bottom-v*220}" width="${bw}" height="${v*220}" rx="5" fill="${s.color}"/>`;
        body+=text(x+bw/2,bottom-(v||0)*220-10,pct(v),'text-anchor="middle" class="chart-value"');
      });
      body+=text(cx,bottom+31,g.label,'text-anchor="middle" class="bar-label"');
    });
    return svg(body,w,h,label)+legend(series.map(s=>[s.label,s.color]));
  }
  function histogram(values,label,log=false) {
    const w=380,h=235,left=33,right=18,bottom=189,plotW=w-left-right,maxCount=Math.max(...values.counts);
    let body='';
    [0,.5,1].forEach(v=>{
      const y=bottom-v*140;
      body+=`<line x1="${left}" y1="${y}" x2="${w-right}" y2="${y}" class="chart-grid"/>`+text(left-6,y+4,number(maxCount*v/values.n*100,0)+'%','text-anchor="end" class="axis-small"');
    });
    values.counts.forEach((n,i)=>{
      const bh=n/maxCount*140;
      body+=`<rect x="${left+i*plotW/20+1}" y="${bottom-bh}" width="${plotW/20-2}" height="${bh}" rx="2" fill="${log?COLORS.das:COLORS.all}"/>`;
    });
    body+=text(left,214,'0','class="axis-small"')+text(w-right,214,number(values.max,log?2:0),'text-anchor="end" class="axis-small"');
    body+=text(w/2,22,label,'text-anchor="middle" class="diagram-title"');
    return svg(body,w,h,label);
  }

  function createDeck(payload) {
    const {content,data}=payload;
    const slides=content.slides.filter(s=>s.enabled!==false);
    const byId=new Map(slides.map(s=>[s.id,s]));
    const groups=content.stages.map(g=>({...g,slides:slides.filter(s=>s.stage===g.id)})).filter(g=>g.slides.length);
    const appendix=slides.filter(s=>s.stage==='appendix');
    const allGroups=[...groups,...(appendix.length?[{id:'appendix',short:'Phụ lục',title:'Phụ lục',slides:appendix}]:[])];
    const fallback=byId.has('pipeline')?'pipeline':slides[0]?.id;
    const row=(key,source='mean_over_sources')=>data.methods[key].evaluation.find(r=>r.dataset_id===source);
    const resolveId=hash=>{
      let id;
      try { id=decodeURIComponent(String(hash||'').replace(/^#/,'')); } catch (_) { return fallback; }
      return byId.has(id)?id:fallback;
    };
    const neighbor=(id,step)=>slides[Math.max(0,Math.min(slides.length-1,slides.findIndex(s=>s.id===resolveId(id))+step))]?.id;
    const stageOf=slide=>allGroups.find(s=>s.id===slide.stage);
    const sourceSelect=(value,full=false)=>select('source','Nguồn đánh giá',Object.entries(SOURCE_LABELS).filter(([k])=>full||!['worst_source','pooled_predictions'].includes(k)),value);
    const metricSelect=(value)=>select('metric','Chỉ số',Object.entries(METRICS),value);
    const methodSelect=(value)=>select('method','Mô hình',ORDER.map(k=>[k,LABELS[k]]),value);
    const testSelect=(value)=>select('testSource','Nguồn test',data.sources.map(s=>[s,SOURCE_LABELS[s]]),value);
    const sourceCaption=source=>`<p class="figure-caption">${esc(SOURCE_LABELS[source])} · profile main · seed 0 · ${source==='pooled_predictions'?'Metric tính lại từ dự đoán gộp':source==='worst_source'?'Cực trị theo từng chỉ số, không phải một nguồn duy nhất':'Các metric nhị phân dùng ngưỡng 0,5'}.</p>`;
    const methodBars=(keys,metric,source)=>barChart(keys.map(k=>({label:LABELS[k],value:row(k,source)[metric],color:COLORS[k]})),{label:`${METRICS[metric]} · ${SOURCE_LABELS[source]}`});
    const visuals=Visuals?.create({data,content,groups,byId,row,assets:payload.assets||{}});
    const tags=(items,cls='')=>`<div class="dataset-tags ${cls}">${items.map(label=>`<span>${esc(label)}</span>`).join('')}</div>`;
    const citation=(dataset,label)=>`<p class="dataset-citation"><a href="${esc(dataset.official_url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a></p>`;

    function home() {
      if(visuals)return visuals.home();
      return `<section class="home-hero"><div><p class="eyebrow"><span class="live-dot"></span> ĐỒ ÁN AN TOÀN THÔNG TIN · MULTIDATASET V1</p><h1>Từ dữ liệu phân tán<br>đến <em>mô hình học liên kết.</em></h1><p class="home-intro">Theo dấu một flow mạng qua chín giai đoạn — từ chuẩn bị dữ liệu đến kiểm chứng kết quả.</p></div><div class="home-spec"><span>CIC-DDoS2019 <b>+</b> UNSW-NB15</span><strong>2 client <i>/</i> 3 lớp</strong><small>ResVGG-SwinNet · FedAvg · FedProx</small></div></section>`+
        `<div class="pipeline-label"><span>PIPELINE TOÀN BỘ BÀI LÀM</span><span>Bấm một giai đoạn để trình bày <span aria-hidden="true">↘</span></span></div>`+
        `<div class="pipeline-grid">${groups.map(g=>{
          const original=content.stages.findIndex(x=>x.id===g.id),positions=[[1,1],[1,2],[1,3],[2,3],[2,2],[2,1],[3,1],[3,2],[3,3]],pos=positions[original];
          const dir=[2,5].includes(original)?'down':[3,4].includes(original)?'left':'right';
          return `<a class="stage-card stage-${g.id}" style="--grid-row:${pos[0]};--grid-col:${pos[1]}" href="#${g.slides[0].id}"><span class="stage-index">${String(original+1).padStart(2,'0')}</span><div><h2>${esc(g.title)}</h2><p>${esc(g.description)}</p></div><span class="stage-pages">${g.slides.length} trang ↗</span>${groups.length===9&&original<8?`<span class="flow-arrow ${dir}" aria-hidden="true">${dir==='down'?'↓':dir==='left'?'←':'→'}</span>`:''}</a>`;
        }).join('')}</div><div class="home-foot"><span><span class="accent">●</span> Kết quả đối chứng nằm trong giai đoạn 08</span><div>${appendix.length?`<a href="#${appendix[0].id}">Phụ lục & phản biện ↗</a>`:''}<a class="start-link" href="#${groups[0]?.slides[0].id||fallback}">Bắt đầu trình bày →</a></div></div>`;
    }

    function distributions(partition='train') {
      let html=controls(select('partition','Tập dữ liệu',[['train','Train'],['val','Validation'],['test','Test']],partition));
      html+=data.sources.map(source=>{
        const counts=data.quality.used_counts[source][partition],total=Object.values(counts).reduce((a,b)=>a+b,0);
        return panel(`<div class="panel-heading"><h3>${SOURCE_LABELS[source]}</h3><span>n = ${number(total)}</span></div><div class="stacked-bar">${CLASS_NAMES.map((c,i)=>counts[c]?`<div style="width:${counts[c]/total*100}%;background:${CLASS_COLORS[i]}" title="${c}: ${number(counts[c])}">${counts[c]/total>.12?pct(counts[c]/total):''}</div>`:'').join('')}</div><div class="class-counts">${CLASS_NAMES.map((c,i)=>`<span><i style="background:${CLASS_COLORS[i]}"></i>${CLASS_SHORT[i]} <b>${number(counts[c]||0)}</b></span>`).join('')}</div>`);
      }).join('');
      return html+`<p class="figure-caption">Số mẫu thật sau lấy subset · không sinh mẫu · các tỷ lệ được tính trong từng nguồn.</p>`;
    }

    function featureRanking(state,full=false) {
      const rankSource=state.rankingSource||'pooled',key=`relevance_${rankSource}`;
      const rows=data.feature_ranking;
      const chooser=controls(select('rankingSource','Relevance hiển thị',[['pooled','Gộp train hai nguồn'],['cicddos2019','Riêng CIC'],['unsw_nb15','Riêng UNSW']],rankSource));
      if(full) return table(['Hạng','Đặc trưng','Gộp','CIC','UNSW','DAS / Lý do'],rows.map(r=>[number(r.rank),`<code>${esc(r.feature)}</code>`,number(r.relevance_pooled,6),number(r.relevance_cicddos2019,6),number(r.relevance_unsw_nb15,6),r.status==='selected'?pill('Giữ','good'):esc(r.reason)]),'dense');
      const max=Math.max(...rows.map(r=>r[key]))*1.15,left=210,width=505,rowH=23,h=rows.length*rowH+48;
      let body='';
      rows.forEach((r,i)=>{
        const y=23+i*rowH,v=r[key],color=r.status==='selected'?COLORS.das:COLORS.all;
        body+=text(left-12,y+4,r.feature,'text-anchor="end" class="rank-label"')+`<rect x="${left}" y="${y-10}" width="${v/max*width}" height="14" rx="3" fill="${color}"/>`+text(left+v/max*width+6,y+3,number(v,4),'class="rank-value"');
      });
      return chooser+svg(body,800,h,'Relevance từng đặc trưng; màu theo quyết định DAS pooled')+legend([['Giữ bởi DAS pooled',COLORS.das],['Loại bởi DAS pooled',COLORS.all]])+`<p class="figure-caption">Thứ hạng và màu quyết định luôn theo pooled; bộ chọn chỉ thay số relevance được vẽ.</p>`;
    }

    function learningCurve(key='das') {
      const rows=data.methods[key].rounds,best=maxRow(rows,'val_score'),w=800,h=337,left=58,right=24,top=29,bottom=274,pw=w-left-right,ph=bottom-top;
      const lines=[['val_f1mp_pid0','CIC',CLASS_COLORS[0]],['val_f1mp_pid1','UNSW',CLASS_COLORS[2]],['val_score','Trung bình','#b8ef78']];
      let body='';
      for(let t=0;t<=4;t++){
        const y=bottom-t*ph/4;
        body+=`<line x1="${left}" y1="${y}" x2="${w-right}" y2="${y}" class="chart-grid"/>`+text(left-10,y+5,`${t*25}%`,'text-anchor="end" class="axis-label"');
      }
      for(const t of [1,5,10,15,20,25,30]) body+=text(left+(t-1)/29*pw,bottom+23,String(t),'text-anchor="middle" class="axis-label"');
      const bx=left+(best.round-1)/29*pw;
      body+=`<line x1="${bx}" y1="${top}" x2="${bx}" y2="${bottom}" stroke="#b8ef78" stroke-dasharray="5 5" opacity=".6"/>`+text(Math.max(110,Math.min(w-110,bx)),17,`Best vòng ${best.round}: ${pct(best.val_score)}`,'text-anchor="middle" class="chart-value"');
      lines.forEach(([metric,label,color])=>{
        body+=`<polyline points="${rows.map(r=>`${left+(r.round-1)/29*pw},${bottom-r[metric]*ph}`).join(' ')}" fill="none" stroke="${color}" stroke-width="2.7" stroke-linejoin="round"/>`;
        body+=`<circle cx="${bx}" cy="${bottom-best[metric]*ph}" r="4" fill="${color}"/>`;
      });
      body+=text(w/2,329,'Vòng huấn luyện · 30 vòng · toàn bộ là validation','text-anchor="middle" class="axis-label"');
      return svg(body,w,h,`Lịch sử validation 30 vòng của ${LABELS[key]}, best vòng ${best.round}`)+legend(lines.map(l=>[l[1],l[2]]));
    }
    function maxRow(rows,key) { return rows.reduce((best,r)=>r[key]>best[key]?r:best,rows[0]); }

    function confusion(state={},withOriginal=false) {
      const method=state.method||'prox',source=state.testSource||'cicddos2019',mode=state.matrixMode||'percent';
      const m=data.methods[method],entries=m.confusion.filter(r=>r.dataset_id===source);
      const counts=CLASS_NAMES.map(a=>CLASS_NAMES.map(b=>entries.find(r=>r.true===a&&r.pred===b).n));
      const per=m.per_class.filter(r=>r.dataset_id===source);
      const size=75,x0=133,y0=61,w=475,h=337;
      let body=text(250,21,'Nhãn dự đoán (argmax)','text-anchor="middle" class="axis-label"');
      CLASS_SHORT.forEach((c,i)=>{
        body+=text(x0+i*size+size/2,47,c,'text-anchor="middle" class="matrix-label"')+text(x0-13,y0+i*size+size/2+5,c,'text-anchor="end" class="matrix-label"');
      });
      counts.forEach((r,i)=>{
        const total=r.reduce((a,b)=>a+b,0);
        r.forEach((n,j)=>{
          const value=total?n/total:null;
          body+=`<rect x="${x0+j*size}" y="${y0+i*size}" width="${size-4}" height="${size-4}" rx="6" fill="${total?`rgba(86,216,233,${.07+value*.85})`:'#1c2533'}"/>`+
            text(x0+j*size+(size-4)/2,y0+i*size+size/2+2,total?(mode==='count'?number(n):`${number(value*100,1)}%`):'N/A','text-anchor="middle" class="matrix-value"');
        });
      });
      body+=text(250,317,'Hàng = nhãn thật · n = 50.000','text-anchor="middle" class="axis-label"');
      let html=controls(methodSelect(method),testSelect(source),select('matrixMode','Ô ma trận',[['percent','Tỷ lệ theo hàng'],['count','Số mẫu']],mode));
      html+=`<div class="matrix-layout">${panel(svg(body,w,h,`Ma trận nhầm lẫn ${LABELS[method]}, ${SOURCE_LABELS[source]}`))}${panel(`<h3>Recall theo lớp</h3>${per.map(r=>`<div class="recall-row"><span>${esc(r.class)}</span><strong>${pct(r.recall)}</strong><div class="small-track"><i style="width:${(r.recall||0)*100}%"></i></div><small>support ${number(r.support)}${!r.support?' · không có mẫu thật':''}</small></div>`).join('')}`)}</div>`;
      html+=`<p class="figure-caption">FAR nhị phân dùng ngưỡng 0,5 trên xác suất; không đồng nhất với sai số BENIGN trong ma trận argmax này.</p>`;
      if(withOriginal) html+=table(['Nhãn gốc','n','Nhóm thật','Nhận là attack','Nhận là DoS'],m.original_labels.filter(r=>r.dataset_id===source).map(r=>[esc(r.original_label),number(r.n),esc(r.true_class),pct(r.attack_detect_rate),pct(r.dos_detect_rate)]),'dense');
      return html;
    }

    function renderView(slide,state={}) {
      const illustrated=visuals?.render(slide,state);
      if(illustrated!=null)return illustrated;
      const source=state.source||'mean_over_sources',metric=state.metric||'f1_macro_present';
      switch(slide.view) {
        case 'home': return home();
        case 'dataset-overview': {
          const catalog=data.dataset_catalog;
          return `<div class="dataset-overview-grid">${data.sources.map(source=>{
            const d=catalog[source];
            return panel(`<span class="eyebrow">${source==='cicddos2019'?'DDoS · UNB / CIC':'XÂM NHẬP MẠNG · UNSW CANBERRA'}</span><h3>${esc(d.title)}</h3><p class="dataset-purpose">${esc(d.purpose)}</p><div class="dataset-scale"><strong>${number(d.local_rows)}</strong><span>flow trong bản đang dùng</span></div><div class="dataset-facts"><span><b>${d.local_columns}</b> cột</span><span><b>${d.local_files}</b> file ${source==='cicddos2019'?'Parquet':'CSV'}</span><span><b>${d.local_measurements}</b> đặc trưng</span></div><p class="dataset-version">${source==='cicddos2019'?'Thu trong 2 ngày: 12/01 và 11/03/2019.':'Training-set: 175.341 · Testing-set: 82.332.'}</p><p class="dataset-original">${source==='cicddos2019'?'Bản Parquet đã làm sạch; mô tả benchmark gốc có hơn 80 đặc trưng.':'Benchmark đầy đủ: 2.540.044 mẫu, 49 trường; bài dùng hai CSV phân hoạch có sẵn.'}</p>${citation(d,source==='cicddos2019'?'UNB · CIC-DDoS2019':'UNSW · UNSW-NB15')}`,'dataset-summary');
          }).join('')}</div><div class="evaluation-size"><span>TEST TRONG THÍ NGHIỆM</span><strong>50.000 CIC <b>+</b> 50.000 UNSW <b>=</b> 100.000 flow</strong><small>Subset đánh giá sau xử lý; không phải toàn bộ số mẫu benchmark.</small></div>`;
        }
        case 'cic-profile': {
          const d=data.dataset_catalog.cicddos2019;
          return `<div class="stat-row">${mini('Bản Parquet đang dùng',number(d.local_rows),'flow mạng')}${mini('Cấu trúc mỗi file',`${d.local_columns} cột`,'77 đặc trưng + Label')}${mini('Số file / Ngày thu',`${d.local_files} / 2`,'thu thập trong testbed')}</div><div class="capture-days">${d.days.map((day,i)=>panel(`<div class="capture-day-heading"><h3>${day.date}</h3>${pill(day.role,i===0?'':'purple')}</div><div class="capture-day-size">${number(day.rows)} mẫu <span>· ${day.files} file</span></div>${tags(day.local_attacks)}<p class="dataset-normal">+ Lưu lượng bình thường (BENIGN)</p>${i===0?'<p class="dataset-day-note">Benchmark gốc còn mô tả SSDP; bản Parquet hiện tại không có nhãn SSDP.</p>':''}`)).join('')}</div><div class="dataset-field-groups"><span>CÁC NHÓM ĐẶC TRƯNG</span>${tags(d.feature_groups,'field-tags')}</div><p class="dataset-context">Nền lưu lượng mô phỏng 25 người dùng: web, FTP, SSH và email. PCAP → CICFlowMeter-V3 → các bản ghi flow.</p>${citation(d,'Nguồn benchmark · Canadian Institute for Cybersecurity')}`;
        }
        case 'unsw-profile': {
          const d=data.dataset_catalog.unsw_nb15;
          return `<div class="stat-row">${mini('Benchmark đầy đủ',number(d.official_rows),'bản ghi trong 4 CSV gốc')}${mini('Schema benchmark',`${d.official_columns} trường`,'theo mô tả của UNSW')}${mini('Nhóm tấn công',String(d.attacks.length),'+ lưu lượng Normal')}</div><div class="unsw-profile-grid">${panel(`<h3>Chín nhóm tấn công</h3>${tags(d.attacks,'attack-grid')}<p class="dataset-normal">+ Normal: lưu lượng bình thường</p>`)}${panel(`<h3>Hai CSV được sử dụng trong bài</h3>${table(['Tập có sẵn','Số mẫu','Dùng làm'],d.splits.map(s=>[esc(s.name),number(s.rows),esc(s.role)]))}<div class="dataset-columns"><strong>45 cột</strong><span>42 đặc trưng + id + attack_cat + label</span></div>`)}</div><div class="dataset-field-groups"><span>CÁC NHÓM ĐẶC TRƯNG</span>${tags(d.feature_groups,'field-tags')}</div><p class="dataset-context">IXIA PerfectStorm tạo lưu lượng → tcpdump thu 100 GB PCAP → Argus / Bro-IDS trích xuất đặc trưng.</p>${citation(d,'Nguồn benchmark · UNSW Canberra')}`;
        }
        case 'schema': return table(['CIC-DDoS2019','Schema chung','UNSW-NB15'],[
          ['Flow Duration','duration_s','dur'],['Total Fwd Packets','fwd_packets','spkts'],['Total Backward Packets','bwd_packets','dpkts'],['Fwd Packets Length Total','fwd_bytes','sbytes'],['Bwd Packets Length Total','bwd_bytes','dbytes'],['Fwd IAT Mean','fwd_iat_mean_s','sinpkt'],['Bwd IAT Mean','bwd_iat_mean_s','dinpkt'],['Protocol','protocol_group','proto']
        ].map(r=>r.map(esc)))+`<div class="metadata-strip">Metadata để truy vết: <code>dataset_id · capture_id · row_id · original_label · fingerprint</code><b>Không đưa vào vector học</b></div>`;
        case 'units': return `<div class="unit-grid">${panel(`<h3>Thời lượng</h3><div class="unit-equation">2.000.000 µs <b>→</b> 2 s</div><small>CIC: chia 10⁶ · UNSW dur: giữ giây</small>`)}${panel(`<h3>IAT trung bình</h3><div class="unit-equation">2.000 ms <b>→</b> 2 s</div><small>UNSW: chia 10³ · CIC: chia 10⁶</small>`)}</div>`+table(['Biểu diễn nguồn','Quy ước chung','Ý nghĩa'],[['6 hoặc tcp',pill('TCP'),'Giao thức TCP'],['17 hoặc udp',pill('UDP'),'Giao thức UDP'],['Normal / BENIGN',pill('BENIGN','good'),'Bình thường'],['DoS / DrDoS_DNS / SYN',pill('DOS_DDOS','warm'),'DoS hoặc DDoS'],['Exploits / Generic / …',pill('OTHER_ATTACK','purple'),'Tấn công khác']])+`<p class="figure-caption">Các phép chuyển đổi số phía trên là ví dụ minh họa. Quy tắc xử lý lấy từ adapter.</p>`;
        case 'quality': {
          const q=data.quality,totalIssues=q.issues.reduce((a,r)=>a+r.n,0),drops=Object.values(q.drops).flat().reduce((a,r)=>a+r.n,0);
          return `<div class="stat-row">${mini('Nhãn lạ / mâu thuẫn',number(totalIssues),'issues quan sát được')}${mini('Dòng bị loại',number(drops),'theo drops của lần chuẩn bị')}${mini('Duration thiếu','0%','ở cả hai nguồn / ba tập')}</div>`+table(['Tình huống','Cách xử lý'],[['Số gói âm, không hữu hạn; tổng ≤ 0','Loại dòng và ghi lý do'],['Duration, byte, IAT âm / không hữu hạn','Đánh dấu missing'],['Một chiều có ít hơn 2 gói','IAT chiều đó = missing'],['Nhãn lạ hoặc mâu thuẫn','Dừng pipeline, ghi quality report']])+`<p class="figure-caption">Quy tắc xử lý ≠ số lỗi đã xảy ra. Báo cáo hiện tại có issues/drops rỗng.</p>`;
        }
        case 'clients': return `<div class="client-boundaries">${data.clients.map((c,i)=>`<div class="client-boundary"><div class="client-head">CLIENT ${i+1}<span>partition ${c.partition_id}</span></div><h3>${SOURCE_LABELS[c.dataset_id]}</h3><div class="client-files">${mini('Train',number(c.n_train))}${mini('Validation',number(c.n_val))}${mini('Test',number(c.n_test))}</div><small>${i===0?'BENIGN · DOS_DDOS':'BENIGN · DOS_DDOS · OTHER_ATTACK'}</small></div>`).join('')}</div>`+panel(`<div class="server-line"><span>CLIENT 1</span><b>⇄</b><strong>SERVER · MÔ HÌNH CHUNG</strong><b>⇄</b><span>CLIENT 2</span></div><p class="figure-caption">Ranh giới logic của mô phỏng. Client huấn luyện lần lượt trên cùng hạ tầng GPU của một experiment.</p>`);
        case 'split': return flow([['Nguồn dữ liệu','Test giữ riêng'],['Pool train','Fingerprint + nhãn'],['5 fold theo nhóm','4 train · 1 validation'],['Lấy subset','Rồi mới fit tham số']])+`<div class="two-col">${panel(`<h3>Nhóm trùng vector ở cùng phía</h3><div class="folds">${[0,1,2,3,4].map((x)=>`<div class="fold ${x===0?'validation':''}">Fold ${x+1}<b>${x===0?'VAL':'TRAIN'}</b></div>`).join('')}</div><small>Chọn fold đầu có đủ lớp của nguồn. Hình minh họa vai trò fold, không phải kích thước cuối.</small>`)}${panel(`<h3>Ba vai trò tách biệt</h3><dl><dt>Train</dt><dd>Fit tham số và học mô hình</dd><dt>Validation</dt><dd>Chọn checkpoint / siêu tham số</dd><dt>Test</dt><dd>Đánh giá mô hình đã chốt</dd></dl>`)}</div>`;
        case 'sampling': return table(['Nguồn / Tập','BENIGN','DOS_DDOS','OTHER','Tổng'],data.sources.flatMap(s=>['train','val','test'].map(sp=>{
          const c=data.quality.used_counts[s][sp];return [`${s==='cicddos2019'?'CIC':'UNSW'} · ${sp}`, ...CLASS_NAMES.map(k=>number(c[k]||0)),number(Object.values(c).reduce((a,b)=>a+b,0))];
        })))+`<div class="callout warm">UNSW train / DoS: 9.811 mẫu thật &lt; sàn 10.000 → giữ toàn bộ, không nhân bản.</div>`;
        case 'feature-map': return `<div class="feature-equation"><div><strong>8</strong><span>trường cơ sở</span></div><b>→</b><div><strong>17</strong><span>cột liên tục</span></div><b>+</b><div><strong>6</strong><span>cột cố định</span></div><b>=</b><div class="accent"><strong>23</strong><span>đầu vào ALL</span></div></div>`+table(['Nhóm','Đặc trưng minh họa'],[['Lượng dữ liệu','fwd_packets · bwd_packets · total_bytes'],['Tốc độ','flow_packets_s · flow_bytes_s'],['Tỷ lệ','bwd_packet_fraction · bwd_byte_fraction'],['Kích thước / IAT','fwd_packet_size_mean · fwd_iat_mean_s'],['Cột cố định','proto_tcp/udp/icmp/other · duration_missing/zero']]);
        case 'feature-example': {
          const mode=state.example||'normal',dur=mode==='zero'?0:2,bwd=mode==='no-bwd'?0:2,bb=bwd?400:0;
          return controls(select('example','Ví dụ minh họa',[['normal','Flow hợp lệ'],['zero','Thời lượng bằng 0'],['no-bwd','Không có gói chiều về']],mode))+`<div class="code-sample"><span>FLOW GIẢ ĐỊNH · KHÔNG PHẢI SỐ LIỆU ĐO</span><code>duration = ${dur} s · fwd_packets = 8 · bwd_packets = ${bwd}<br>fwd_bytes = 800 · bwd_bytes = ${bb} · protocol = TCP</code></div>`+table(['Đặc trưng','Phép tính','Kết quả'],[['total_packets',`8 + ${bwd}`,number(8+bwd)],['flow_packets_s',`${8+bwd} / ${dur}`,dur?`${number((8+bwd)/dur,1)} gói/s`:'missing'],['flow_bytes_s',`${800+bb} / ${dur}`,dur?`${number((800+bb)/dur)} byte/s`:'missing'],['fwd_packet_size_mean','800 / 8','100 byte/gói'],['bwd_packet_size_mean',`${bb} / ${bwd}`,bwd?'200 byte/gói':'missing'],['duration_zero',`${dur} = 0 ?`,dur?'0':'1']]);
        }
        case 'logarithm': return `<div class="log-examples"><span>0 <b>→</b> 0</span><span>999 <b>→</b> 6,91</span><span>999.999 <b>→</b> 13,82</span></div><div class="two-col histogram-pair">${panel(histogram(data.histogram.raw,'Trước log1p · giây'))}${panel(histogram(data.histogram.log,'Sau log1p · ln(1 + giây)',true))}</div><p class="figure-caption">${esc(data.histogram.note)} Trục dọc là tỷ lệ số mẫu mỗi bin, trục ngang có miền khác nhau.</p>`;
        case 'afn': return formula('z[j] = (log1p(x[j]) − mean[protocol, j]) / scale[protocol, j]')+flow([['Client 1 & 2','n_valid · sum · sumsq'],['Gộp theo protocol','mean / std từ train'],['Giữ tham số','std ≈ 0 → scale = 1'],['Transform','train · validation · test']])+table(['Nhóm train','Số flow'],Object.entries(data.afn.groups).filter(([k])=>k!=='__all__').map(([k,v])=>[k.toUpperCase(),number(v.n_rows)]))+`<div class="callout">Missing → z = 0 · nhóm không có thống kê phù hợp → tham số train toàn cục dự phòng.</div>`;
        case 'das': return flow([['CRA','Xếp relevance ↓'],['Ngưỡng liên quan','Relevance > 0,001'],['IDF','|corr| < 0,9'],['Giới hạn','Tối đa 12 cột']])+formula('relevance(x) = mean_c [ Cov(x, 1[y=c])² / (Var(x) · Var(1[y=c])) ]')+`<div class="three-col">${mini('Nguồn thống kê','TRAIN','gộp hai client')}${mini('Đầu ra chọn','12','cột liên tục')}${mini('Cột cố định','6','giữ riêng ngoài DAS')}</div>`;
        case 'ranking': return featureRanking(state);
        case 'feature-sets': return `<div class="two-col feature-comparison">${panel(`<span class="eyebrow">ĐỐI CHỨNG</span><h3>ALL</h3><strong class="big-count">23</strong><p>17 liên tục + 6 cố định</p><div class="feature-dots">${Array.from({length:23},(_,i)=>`<i class="${i>=17?'fixed':''}"></i>`).join('')}</div>`)}${panel(`<span class="eyebrow">LỰA CHỌN ĐẶC TRƯNG</span><h3>DAS</h3><strong class="big-count accent">18</strong><p>12 liên tục + 6 cố định</p><div class="feature-dots">${Array.from({length:18},(_,i)=>`<i class="${i>=12?'fixed':''}"></i>`).join('')}</div>`)}</div><div class="callout">✓ Cùng hash split → cùng mẫu và cách chia · cùng ngân sách FedAvg</div><p class="figure-caption">Hash schema/preprocessor khác theo bộ cột. Giảm đầu vào không đồng nghĩa giảm tương ứng tổng chi phí mô hình.</p>`;
        case 'architecture': return flow([['Vector F','18 hoặc 23'],['Linear','Lưới học 8×8'],['ResNet','2 residual block'],['VGG','2 conv 3×3'],['Swin + Head','3 logits']])+`<div class="architecture-detail">${panel(`<h3>Residual learning</h3>${formula('F(z) + z')}<p>32 kênh · đường nối tắt · GroupNorm</p>`)}${panel(`<h3>Window attention</h3>${formula('W-MSA → SW-MSA')}<p>Cửa sổ 4×4 · dịch 2 · 4 heads</p>`)}</div><p class="figure-caption">8×8 là biểu diễn được học từ vector. Không phải ảnh đầu vào hoặc bản đồ không gian tự nhiên của flow.</p>`;
        case 'forward': return table(['Thành phần','Kích thước tensor','Chức năng'],[['Vector đầu vào','B × F','F = 18 hoặc 23'],['Linear + reshape','B × 1 × 8 × 8','Chiếu thành lưới'],['ResNet','B × 32 × 8 × 8','Trích xuất với residual'],['VGG','B × 64 × 8 × 8','Hai convolution 3×3'],['Swin','B × 64 token × 64 chiều','Quan hệ giữa token'],['Mean pooling → Head','B × 64 → B × 3','Ba logits']])+`<div class="callout">Forward trả logits. CrossEntropyLoss nhận logits trực tiếp; softmax được tính khi dự đoán.</div>`;
        case 'methods': return `<div class="method-columns">${[['Local-only','Mỗi nguồn → mô hình riêng','Không trao đổi dữ liệu / mô hình','A → wA  |  B → wB'],['Centralized','Gộp train → một mô hình','Cần tập trung dữ liệu train','A + B → w'],['Federated','Client học → server gộp','Trao đổi cập nhật mô hình','w → A/B → Δw → w′']].map((x,i)=>panel(`<span class="method-index">0${i+1}</span><h3>${x[0]}</h3><div class="method-mini-diagram">${esc(x[3])}</div><p>${x[1]}</p><small>${x[2]}</small>`,i===2?'highlight':'')).join('')}</div><div class="callout">Cùng kiến trúc tổng quát. Hiệu quả dự đoán và khả năng tổng quát được kiểm chứng trong giai đoạn 08.</div>`;
        case 'round': {
          const step=Number(state.step||0),steps=[['Server gửi mô hình','Cùng w_global cho cả hai client'],['Client học cục bộ','5 epoch · weighted cross-entropy · Adam'],['Client gửi trọng số','Kèm số mẫu và phản hồi đúng PID'],['Server tổng hợp','FedAvg rồi đánh giá validation']];
          return `<div class="step-tabs" role="group" aria-label="Các bước một vòng FedAvg">${steps.map((s,i)=>`<button data-action="step" data-value="${i}" aria-pressed="${step===i}">${i+1}. ${s[0]}</button>`).join('')}</div>${panel(`<span class="eyebrow">BƯỚC ${step+1} / 4</span><h3>${steps[step][0]}</h3><p class="step-description">${steps[step][1]}</p><div class="round-diagram"><span class="${step===1?'active':''}">CLIENT 1<br><small>CIC · n = 100.000</small></span><b>${step===0?'←':'→'}</b><strong class="${[0,3].includes(step)?'active':''}">SERVER<br><small>30 vòng</small></strong><b>${step===0?'→':'←'}</b><span class="${step===1?'active':''}">CLIENT 2<br><small>UNSW · n = 100.000</small></span></div>`)}${formula('w(t+1) = Σ [ nₖ / (n₁ + n₂) ] · wₖ(t+1) = 0,5 w₁ + 0,5 w₂')}<p class="figure-caption">Class weight trong loss: CIC [1,5314; 0,4686; 0] · UNSW [0,5901; 2,0511; 0,3588]. Khác trọng số tổng hợp client.</p>`;
        }
        case 'experiments': return table(['Cấu hình','Đầu vào','Ngân sách','Chọn best theo'],[['2 mô hình local','DAS · 18','150 epoch / nguồn','Val nguồn đã học'],['Centralized','DAS · 18','150 epoch','TB F1-macro 2 val'],['FedAvg','ALL · 23','30 × 5 epoch','TB F1-macro 2 val'],['FedAvg','DAS · 18','30 × 5 epoch','TB F1-macro 2 val'],['FedProx μ=0,1','DAS · 18','30 × 5 epoch','TB F1-macro 2 val']])+flow([['Train','Học mô hình'],['Validation','Chọn best checkpoint'],['Chốt trọng số','Không chọn bằng test'],['Hai test','Cùng một checkpoint']])+`<p class="figure-caption">Seed 0 duy nhất. Mốc epoch không chứng minh cùng FLOPs hoặc thời gian; GPU FedAvg/baseline và FedProx khác nhau.</p>`;
        case 'metrics': return table(['Nhiệm vụ','Quy tắc quyết định','Chỉ số'],[['Ba lớp','argmax P(c)','F1-macro-present · accuracy'],['Mọi tấn công','1 − P(BENIGN) ≥ 0,5','attack-F1 · recall · FAR trên benign'],['DoS/DDoS','P(DOS_DDOS) ≥ 0,5','dos-F1 · recall · FAR trên benign']])+`<div class="two-col">${panel(`<h3>Trung bình đều theo nguồn</h3>${formula('(metric_CIC + metric_UNSW) / 2')}<small>CIC macro trên 2 lớp thật; UNSW trên 3 lớp thật.</small>`)}${panel(`<h3>Pooled predictions</h3><p>Gộp dự đoán hai test, sau đó tính lại chỉ số.</p><small>Không lấy trung bình hai F1 để gọi là pooled.</small>`)}</div>`;
        case 'baseline': return controls(sourceSelect(source),metricSelect(metric))+methodBars(['local_cic','local_unsw','central','das'],metric,source)+sourceCaption(source);
        case 'transfer': return controls(metricSelect(metric))+table(['Mô hình / nguồn đã học','Test CIC','Test UNSW','TB hai nguồn'],['local_cic','local_unsw','das','central'].map(k=>[`<span class="method-dot" style="--method-color:${COLORS[k]}"></span>${LABELS[k]}`,...['cicddos2019','unsw_nb15','mean_over_sources'].map(s=>`<span class="heat-value" style="--heat:${row(k,s)[metric]||0}">${pct(row(k,s)[metric])}</span>`)]))+`<div class="callout">Điểm local trên nguồn riêng có thể cao. Kết luận học chung ở đây xét một mô hình hoạt động trên cả hai nguồn.</div>`;
        case 'all-das': return controls(metricSelect(metric))+groupedChart(['cicddos2019','unsw_nb15','mean_over_sources'].map(s=>({label:s==='mean_over_sources'?'TB hai nguồn':s==='cicddos2019'?'CIC':'UNSW',values:['all','das'].map(k=>row(k,s)[metric])})),['all','das'].map(k=>({label:LABELS[k],color:COLORS[k]})),`${METRICS[metric]} · ALL so với DAS`)+`<p class="figure-caption">Cùng subset và ngân sách · ALL best vòng 24, DAS best vòng 4 · mỗi nhánh chọn riêng bằng cùng quy tắc validation.</p>`;
        case 'das-tradeoff': return controls(sourceSelect(source))+table(['Chỉ số','ALL','DAS','DAS − ALL'],['f1_macro_present','dos_f1','attack_f1','attack_recall','dos_recall','attack_far_benign'].map(k=>{
          const delta=(row('das',source)[k]-row('all',source)[k])*100,isGood=k.includes('far')?delta<0:delta>0;
          return [METRICS[k],pct(row('all',source)[k]),pct(row('das',source)[k]),`<span class="${isGood?'positive':'negative'}">${signed(delta)} điểm phần trăm</span>`];
        }))+sourceCaption(source);
        case 'heterogeneity': {
          const k=state.curve||'das';return controls(select('curve','Lịch sử validation',[['das',LABELS.das],['all',LABELS.all],['prox',LABELS.prox]],k))+learningCurve(k)+`<div class="callout">Khác biệt phân phối có thể góp phần làm cập nhật lệch nhau. Biểu đồ chưa xác định duy nhất nguyên nhân.</div>`;
        }
        case 'prox-mechanism': return `<div class="prox-formula"><span>MỤC TIÊU TẠI CLIENT</span>${formula('L(w) = L_local(w) + μ/2 · ‖w − w_global‖²')}<div><span>Học dữ liệu riêng</span><b>+</b><span>Phạt đi xa điểm neo</span></div></div>`+svg(`<circle cx="400" cy="152" r="112" fill="none" stroke="#b8ef78" stroke-dasharray="5 7" opacity=".35"/><circle cx="400" cy="152" r="8" fill="#b8ef78"/><line x1="400" y1="152" x2="168" y2="65" stroke="#94a3b8" stroke-width="3"/><line x1="400" y1="152" x2="637" y2="64" stroke="#94a3b8" stroke-width="3"/><line x1="400" y1="152" x2="333" y2="99" stroke="#56d8e9" stroke-width="5"/><line x1="400" y1="152" x2="470" y2="109" stroke="#56d8e9" stroke-width="5"/>${text(400,184,'w_global đầu vòng','text-anchor="middle" class="diagram-title"')}${text(151,49,'Hướng cục bộ A','text-anchor="middle" class="axis-label"')}${text(651,49,'Hướng cục bộ B','text-anchor="middle" class="axis-label"')}${text(400,278,'Minh họa trực giác · không phải quỹ đạo đo từ thí nghiệm','text-anchor="middle" class="axis-label"')}`,800,300,'Minh họa ràng buộc proximal quanh mô hình toàn cục')+`<p class="figure-caption">μ = 0,1 trong thí nghiệm · server vẫn FedAvg · số hạng neo không phải bộ lọc cập nhật độc hại.</p>`;
        case 'prox-results': return controls(sourceSelect(source),metricSelect(metric))+methodBars(['das','central','prox'],metric,source)+sourceCaption(source)+`<div class="checkpoint-line">FedAvg: best 4 <span>·</span> Centralized: epoch 111 <span>·</span> FedProx: best 18</div>`;
        case 'errors': return confusion(state);
        case 'contributions': return `<div class="contribution-list">${[['01','Pipeline chung','Hai nguồn → schema → chia tập → fit train → huấn luyện → đánh giá.'],['02','Đối chứng có kiểm soát','Giữ cùng mẫu để kiểm tra vai trò của cách học, đặc trưng và proximal.'],['03','Kết quả có điều kiện','Đọc đồng thời nguồn, nhiệm vụ và báo động giả.']].map(r=>`<div><span>${r[0]}</span><h3>${r[1]}</h3><p>${r[2]}</p></div>`).join('')}</div><div class="result-journey">${['all','das','prox'].map(k=>`<div><small>${LABELS[k]}</small><strong style="color:${COLORS[k]}">${pct(row(k).f1_macro_present)}</strong></div>`).join('<b>→</b>')}</div><p class="figure-caption">F1-macro-present trung bình đều hai nguồn · seed 0 · các đánh đổi đã phân tích ở giai đoạn 08.</p>`;
        case 'limits': return table(['Giới hạn quan sát','Bước phát triển tương ứng'],[['Một seed, hai client','Nhiều seed và thêm nguồn / client'],['FAR còn cao ở ngưỡng 0,5','Chọn ngưỡng trên validation theo mục tiêu vận hành'],['DAS giảm một số metric','Kiểm tra lựa chọn đặc trưng và mục tiêu loss'],['Vector trùng với test đã được báo cáo','Rà soát overlap, thêm test độc lập'],['Mô phỏng trên hạ tầng dùng chung','Đánh giá truyền thông, riêng tư, vận hành thực tế']])+`<div class="end-links"><a href="#pipeline">↖ Quay về pipeline</a>${appendix.length?`<a href="#${appendix[0].id}">Mở phụ lục & phản biện →</a>`:''}</div>`;
        case 'appendix-formulas': return table(['Chỉ số','Công thức / Quy tắc'],[['Precision','TP / (TP + FP)'],['Recall','TP / (TP + FN)'],['F1','2TP / (2TP + FP + FN)'],['FAR trên BENIGN','Benign bị báo dương / tổng benign'],['Accuracy','Số dự đoán đúng / tổng mẫu'],['F1-macro-present','Trung bình F1 các lớp có support thật'],['Mean over sources','(metric_CIC + metric_UNSW) / 2'],['Pooled','Tính lại metric từ dự đoán hai nguồn gộp']])+`<div class="callout">DoS-FAR có mẫu số là BENIGN, không phải toàn bộ lớp âm gồm cả OTHER_ATTACK.</div>`;
        case 'appendix-metrics': return controls(sourceSelect(source,true))+table(['Mô hình','Acc','F1 macro','Attack F1','Attack recall','Attack FAR ↓','Attack AUC','DoS F1','DoS recall','DoS FAR ↓','DoS AUC','Best'],ORDER.map(k=>[LABELS[k],...['acc','f1_macro_present','attack_f1','attack_recall','attack_far_benign','attack_roc_auc','dos_f1','dos_recall','dos_far_benign','dos_roc_auc'].map(m=>pct(row(k,source)[m])),String(row(k,source).selected_round)]),'dense full-metrics')+sourceCaption(source);
        case 'appendix-confusion': return confusion(state,true);
        case 'appendix-ranking': return featureRanking(state,true);
        case 'appendix-audit': return `<div class="stat-row">${mini('Hai run','COMPLETED')}${mini('Seed / profile','0 / main')}${mini('Cùng bundle',data.bundle_id.slice(0,12)+'…')}</div>`+table(['Nguồn','Trùng nhóm train/val','Vector train có trong test','Vector val có trong test'],data.sources.map(s=>{const q=data.quality.independence[s];return [SOURCE_LABELS[s],number(q.train_val_group_overlap),number(q.train_vectors_also_in_test),number(q.val_vectors_also_in_test)];}))+`<div class="callout warm">Các con số overlap là số fingerprint giao nhau ở tập ứng viên được báo cáo; không tự chứng minh rò rỉ nhãn. Không tuyên bố test độc lập tuyệt đối.</div>`+table(['Run','Vai trò','GPU'],data.runs.map(r=>[esc(r.run_id),r.run_id.includes('193340')?'FedProx':'Local / central / FedAvg',esc(r.jobs.find(j=>j.profile==='main').gpu)]))+`<details class="source-details"><summary>${data.evidence.length} artifact và SHA-256 nguồn</summary>${table(['Artifact','SHA-256'],data.evidence.map(e=>[`<code>${esc(e.path)}</code>`,`<code>${e.sha256}</code>`]),'dense')}</details><div class="references">${data.references.map(r=>`<a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title)} ↗</a>`).join('')}</div>`;
        case 'appendix-qa': return [
          ['Vì sao dùng FL nếu centralized cũng học được?','FL phù hợp với mục tiêu phối hợp mà không tập trung dữ liệu thô trong quy trình. Centralized là đối chứng thực nghiệm. Thí nghiệm hiện tại là mô phỏng, chưa đo một triển khai phân tán thực tế.','train-methods'],
          ['FL có bảo đảm dữ liệu riêng tư tuyệt đối không?','Không. Cập nhật mô hình và thống kê có thể tiết lộ thông tin. Chưa triển khai secure aggregation hoặc differential privacy trong pipeline này.','normalize-afn'],
          ['DAS có thực sự tốt hơn ALL không?','F1-macro trung bình tăng 7,66 điểm phần trăm, nhưng CIC giảm, DoS-F1 trung bình giảm và FAR tăng. Kết luận phải gắn với chỉ số và nguồn.','results-das-tradeoff'],
          ['Vì sao đưa flow vào CNN / Swin?','Linear học biểu diễn 8×8 cho vector flow theo kiến trúc tham khảo. Chưa có ablation đủ trên hai nguồn để khẳng định từng khối đều cần thiết hoặc tối ưu.','train-architecture'],
          ['FedProx có chống client đầu độc không?','Không phải mục tiêu của số hạng proximal. Server vẫn FedAvg; không có cơ chế robust aggregation hoặc thí nghiệm poisoning trong pipeline này.','results-prox-mechanism'],
          ['FedProx có hội tụ ổn định hơn trong mọi vòng không?','Không kết luận như vậy. Hình hiển thị đủ 30 vòng, best ở 18 và điểm cuối có thể giảm. Kết quả test đang so checkpoint tốt nhất theo validation.','results-heterogeneity'],
          ['Có thể coi centralized là cận trên không?','Không có bảo đảm. Trong lượt hiện tại FedProx có F1-macro trung bình cao hơn centralized, nhưng một seed chưa chứng minh ưu thế tổng quát.','results-prox'],
          ['Bằng chứng độc lập train / test đã đủ chưa?','Train/val không trùng nhóm theo kiểm tra. Vẫn có vector trùng với test được báo cáo. Cần rà soát thêm và đánh giá trên dữ liệu độc lập.','appendix-audit'],
          ['Vì sao không chọn ngưỡng tốt nhất bằng test?','Test dùng đánh giá sau khi chốt. Chọn ngưỡng hoặc μ theo validation; cần test độc lập nếu các kết quả test cũ đã được dùng để định hướng thử nghiệm.','conclusion-next']
        ].map(([q,a,link])=>`<details class="qa-item"><summary>${esc(q)}</summary><p>${esc(a)}</p>${byId.has(link)?`<a href="#${link}">Xem slide liên quan →</a>`:''}</details>`).join('');
        default: throw new Error(`Không hỗ trợ view: ${slide.view}`);
      }
    }

    function render(id,state={}) {
      const slide=byId.get(resolveId(id));
      if(!slide) return '<p>Không còn slide nào được bật. Hãy bật lại nội dung trong slides.json.</p>';
      if(slide.view==='home') return home();
      const group=stageOf(slide),idx=group?.slides.indexOf(slide)||0;
      const sectionLabel=slide.stage==='appendix'?'PHỤ LỤC':`GIAI ĐOẠN ${String(content.stages.findIndex(g=>g.id===slide.stage)+1).padStart(2,'0')}`;
      const submenu=slide.stage==='results'?`<nav class="results-nav" aria-label="Các trang kết quả">${group.slides.map(s=>`<a href="#${s.id}" ${s.id===slide.id?'aria-current="page"':''}>${s.number}<span>${esc(s.title)}</span></a>`).join('')}</nav>`:'';
      return `<article class="slide ${slide.stage==='appendix'?'appendix-slide':''}" data-slide="${slide.id}"><header class="slide-heading"><div class="eyebrow"><span>${sectionLabel} · ${esc(group?.title||'')}</span><span>${idx+1} / ${group?.slides.length||1}</span></div><h1>${esc(slide.title)}</h1><p class="slide-message">${esc(slide.message)}</p></header>${submenu}<div class="content-grid full-width"><section class="visual-area" aria-label="Minh họa và số liệu">${renderView(slide,state)}</section></div></article>`;
    }
    function renderMenu(id) {
      return `<div class="drawer-head"><span>DANH MỤC · ${slides.length} TRANG ĐANG BẬT</span><button data-action="close" aria-label="Đóng danh mục">×</button></div><h2>Chọn nơi muốn trình bày</h2>${byId.has('pipeline')?`<a class="menu-home" href="#pipeline" ${id==='pipeline'?'aria-current="page"':''}>00 · Pipeline tổng quan ↗</a>`:''}${allGroups.map(g=>`<section class="menu-group"><h3>${esc(g.title)} <span>${g.slides.length}</span></h3>${g.slides.map(s=>`<a href="#${s.id}" ${s.id===id?'aria-current="page"':''}><span>${s.number}</span>${esc(s.title)}</a>`).join('')}</section>`).join('')}`;
    }
    function nav(id) {
      const slide=byId.get(resolveId(id));
      return groups.map((g,i)=>`<a href="#${g.slides[0].id}" title="${esc(g.title)}" ${slide?.stage===g.id?'aria-current="step"':''}>${String(content.stages.findIndex(x=>x.id===g.id)+1).padStart(2,'0')}<span>${esc(g.short)}</span></a>`).join('');
    }
    return {content,data,slides,groups,appendix,byId,fallback,resolveId,neighbor,row,render,renderMenu,nav,stageOf,renderView};
  }

  function mount(payload) {
    const deck=createDeck(payload),main=document.getElementById('main');
    const stateBySlide={},menu=document.getElementById('slide-menu'),backdrop=document.getElementById('backdrop');
    let activeDrawer=null,opener=null,current=deck.resolveId(location.hash);
    const el=id=>document.getElementById(id);
    function closeDrawer(restore=true) {
      menu.hidden=true;backdrop.hidden=true;
      el('menu-toggle').setAttribute('aria-expanded','false');
      document.body.classList.remove('drawer-open');activeDrawer=null;
      if(restore)opener?.focus();
    }
    function openDrawer() {
      if(activeDrawer){closeDrawer();return;}
      opener=el('menu-toggle');activeDrawer='menu';
      menu.innerHTML=deck.renderMenu(current);
      menu.hidden=false;backdrop.hidden=false;document.body.classList.add('drawer-open');
      el('menu-toggle').setAttribute('aria-expanded','true');
      menu.querySelector('button')?.focus();
    }
    function paint() {
      current=deck.resolveId(location.hash);
      if(location.hash!==`#${current}`) history.replaceState(null,'',`#${current}`);
      const slide=deck.byId.get(current),group=slide&&deck.stageOf(slide),idx=deck.slides.findIndex(s=>s.id===current);
      main.innerHTML=deck.render(current,stateBySlide[current]||{});
      main.scrollTop=0;
      el('stage-nav').innerHTML=deck.nav(current);
      el('position').textContent=group?`${group.title} · ${group.slides.indexOf(slide)+1}/${group.slides.length}`:'Pipeline tổng quan · 9 giai đoạn';
      el('page-number').textContent=`${idx+1} / ${deck.slides.length}`;
      el('progress').style.width=`${(idx+1)/deck.slides.length*100}%`;
      el('previous').disabled=idx===0;el('next').disabled=idx===deck.slides.length-1;
      document.title=`${slide?.number||''} · ${slide?.title||'Thuyết trình'} — Học liên kết`;
      document.body.classList.toggle('is-home',slide?.view==='home');
      if(activeDrawer==='menu')menu.innerHTML=deck.renderMenu(current);
    }
    function go(id) {
      const target=deck.resolveId(id);
      if(target===current)paint();else location.hash=target;
    }
    async function fullscreen() {
      try {
        if(document.fullscreenElement)await document.exitFullscreen();
        else if(document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen();
        else throw new Error('unsupported');
      } catch (_) {
        el('toast').textContent='Trình duyệt chưa bật được toàn màn hình. Bạn có thể dùng F11.';
      }
    }
    el('previous').addEventListener('click',()=>go(deck.neighbor(current,-1)));
    el('next').addEventListener('click',()=>go(deck.neighbor(current,1)));
    el('menu-toggle').addEventListener('click',openDrawer);
    el('fullscreen').addEventListener('click',fullscreen);
    backdrop.addEventListener('click',()=>closeDrawer());
    document.addEventListener('click',event=>{
      const action=event.target.closest('[data-action]');
      if(action?.dataset.action==='close')closeDrawer();
      if(['step','phase'].includes(action?.dataset.action)){
        const key=action.dataset.action;
        stateBySlide[current]={...(stateBySlide[current]||{}),[key]:Number(action.dataset.value)};
        paint();main.querySelector(`[data-action="${key}"][data-value="${action.dataset.value}"]`)?.focus();
      }
      const link=event.target.closest('a[href^="#"]');
      if(link?.getAttribute('href')==='#main'){
        event.preventDefault();main.focus({preventScroll:true});return;
      }
      if(link&&menu.contains(link))closeDrawer(false);
    });
    main.addEventListener('change',event=>{
      const key=event.target.dataset.control;if(!key)return;
      stateBySlide[current]={...(stateBySlide[current]||{}),[key]:event.target.value};
      paint();main.querySelector(`[data-control="${key}"]`)?.focus();
    });
    document.addEventListener('keydown',event=>{
      if(event.key==='Escape'){closeDrawer();return;}
      if(activeDrawer&&event.key==='Tab'){
        const focusables=[...menu.querySelectorAll('a,button,select,summary,[tabindex="0"]')];
        const first=focusables[0],last=focusables.at(-1);
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
        return;
      }
      if(event.altKey||event.ctrlKey||event.metaKey||event.target.closest('input,textarea,select,[contenteditable="true"]'))return;
      if(activeDrawer)return;
      const actions={ArrowRight:()=>go(deck.neighbor(current,1)),PageDown:()=>go(deck.neighbor(current,1)),ArrowLeft:()=>go(deck.neighbor(current,-1)),PageUp:()=>go(deck.neighbor(current,-1)),h:()=>go(deck.fallback),f:fullscreen};
      const action=actions[event.key]||actions[event.key.toLowerCase()];
      if(action){event.preventDefault();action();}
    });
    root.addEventListener('hashchange',()=>{paint();if(!activeDrawer)main.focus({preventScroll:true});});
    paint();return deck;
  }
  const api={createDeck,mount,pct,number,esc,COLORS,LABELS,METRICS};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.Presentation=api;
  if(typeof document!=='undefined'&&document.getElementById('deck-payload')){
    try {root.presentationDeck=mount(JSON.parse(document.getElementById('deck-payload').textContent));}
    catch(error){document.getElementById('main').innerHTML=`<div class="load-error"><h1>Không thể mở bài trình chiếu</h1><p>${esc(error.message)}</p><p>Chạy lại build.py hoặc đọc kich_ban.md.</p></div>`;throw error;}
  }
})(typeof globalThis!=='undefined'?globalThis:this);
