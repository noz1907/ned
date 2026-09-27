(function(){
var sahne=document.getElementById('sahne');
var S=[].slice.call(document.querySelectorAll('.slayt'));
var SURE=S.map(function(s){return +s.dataset.sure});
var BAS=[],t0=0;SURE.forEach(function(d){BAS.push(t0);t0+=d});
var TOPLAM=t0,GECIS=800;
var GECTIP=['kay','patla','yukari','kay','yakin'];
function kel(v){return v<0?0:v>1?1:v}
function cik(p){return 1-Math.pow(1-p,3)}
function geri(p){var c1=1.70158,c3=c1+1;return 1+c3*Math.pow(p-1,3)+c1*Math.pow(p-1,2)}
function oge(el,lt){
  var t=+el.dataset.t||0,d=+el.dataset.d||600,a=el.dataset.a,p=kel((lt-t)/d),e=cik(p);
  var don=el.style.getPropertyValue('--don');var tb=don?'perspective(1800px) rotateY('+don+') ':'';
  if(a==='say'){var h=+el.dataset.hedef;el.textContent=Math.round(h*cik(p)).toLocaleString('tr-TR');return}
  if(a==='uza'){el.style.transform='scaleX('+e+')';return}
  var tr='',op=e;
  if(a==='kaysol')tr='translateX('+(-140*(1-e))+'px)';
  else if(a==='kaysag')tr='translateX('+(140*(1-e))+'px)';
  else if(a==='alt')tr='translateY('+(60*(1-e))+'px)';
  else if(a==='patla'){var g=p<=0?0:geri(p);tr='scale('+(0.25+0.75*g)+')';op=kel(p*2.2)}
  else if(a==='yakin')tr='scale('+(0.8+0.2*e)+')';
  el.style.opacity=op;el.style.transform=tb+tr;
  if(el.classList.contains('vurgu')&&p>=1){var n=0.5+0.5*Math.sin((lt-t-d)/260);
    el.style.boxShadow='0 0 0 3px rgba(0,0,0,.25),0 0 '+(18+26*n)+'px rgba(245,197,24,'+(0.55+0.4*n)+')'}
}
function slaytCiz(i,lt,gecis,rol){
  var s=S[i];s.style.display='block';
  var p=cik(kel(gecis)),tip=GECTIP[i%GECTIP.length],tr='',op=1;
  if(rol==='gelen'&&gecis<1){
    if(tip==='kay'){tr='translateX('+(1920*(1-p))+'px)'}
    else if(tip==='patla'){tr='scale('+(0.6+0.4*geri(kel(gecis)))+')';op=kel(gecis*1.6)}
    else if(tip==='yukari'){tr='translateY('+(1080*(1-p))+'px)'}
    else {tr='scale('+(1.25-0.25*p)+')';op=p}
  }else if(rol==='giden'){
    var q=p;
    if(tip==='kay'){tr='translateX('+(-1920*q)+'px)'}
    else if(tip==='patla'){tr='scale('+(1+0.35*q)+')';op=1-q}
    else if(tip==='yukari'){tr='translateY('+(-360*q)+'px)';op=1-q}
    else {tr='scale('+(1-0.15*q)+')';op=1-q}
  }
  s.style.transform=tr;s.style.opacity=op;s.style.zIndex=rol==='gelen'?2:1;
  var og=s.querySelectorAll('.a');for(var k=0;k<og.length;k++)oge(og[k],lt);
  var kb=s.querySelectorAll('img.kb');for(k=0;k<kb.length;k++)kb[k].style.transform='scale('+(1+0.04*kel(lt/SURE[i]))+')';
}
function ciz(t){
  t=((t%TOPLAM)+TOPLAM)%TOPLAM;
  var i=0;while(i+1<S.length&&BAS[i+1]<=t)i++;
  var lt=t-BAS[i];
  for(var k=0;k<S.length;k++)S[k].style.display='none';
  var g=i>0?lt/GECIS:1;
  if(i>0&&g<1)slaytCiz(i-1,SURE[i-1]+lt,g,'giden');
  slaytCiz(i,lt,g,'gelen');
  document.getElementById('ilerleme').style.width=(100*t/TOPLAM)+'%';
  var f=document.querySelector('.filigran');f.style.transform='translate('+(Math.sin(t/9000)*40)+'px,'+(Math.cos(t/11000)*20)+'px)';
}
function olcek(){var k=Math.min(innerWidth/1920,innerHeight/1080);sahne.style.transform='translate('+((innerWidth-1920*k)/2)+'px,'+((innerHeight-1080*k)/2)+'px) scale('+k+')'}
window.addEventListener('resize',olcek);olcek();
window.ciz=ciz;window.TOPLAM=TOPLAM;
if(location.hash==='#kayit'){ciz(0);return}
var basla=performance.now(),dur=false,durT=0;
function simdi(){return dur?durT:performance.now()-basla}
function git(t){basla=performance.now()-t;durT=t}
function slaytNo(){var t=simdi()%TOPLAM,i=0;while(i+1<S.length&&BAS[i+1]<=t)i++;return i}
document.addEventListener('keydown',function(e){
  if(e.key==='ArrowRight'||e.key==='PageDown'){git(BAS[(slaytNo()+1)%S.length])}
  else if(e.key==='ArrowLeft'||e.key==='PageUp'){git(BAS[(slaytNo()-1+S.length)%S.length])}
  else if(e.key===' '){if(dur){dur=false;git(durT)}else{durT=simdi();dur=true}}
});
sahne.addEventListener('click',function(){git(BAS[(slaytNo()+1)%S.length])});
(function kare(){ciz(simdi());requestAnimationFrame(kare)})();
})();
