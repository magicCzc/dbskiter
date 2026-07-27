import{d as B,h as m,X as E,a as I,c as N,A as C,k as A,l as g,D as y,u as H,o as W,G as h,p as s,m as n,q as e,x,y as T,K as z,B as G}from"./index-DzV7P-Cc.js";import{d as K,h as $,f as b,a5 as q,i as O,P as U,m as X,n as V,y as F,a6 as J,U as Q,A as Y,a0 as Z,a1 as k,R as D,a2 as _,Q as ee,a3 as v}from"./text-DJ5v9n0F.js";import{o as te}from"./Select-WRznkyhc.js";import{N as se}from"./Alert-DA7lj8Yb.js";import{b as ne,a as w,N as S}from"./Statistic-Douu8jVn.js";function ae(r){const{opacityDisabled:d,heightTiny:a,heightSmall:o,heightMedium:i,heightLarge:c,heightHuge:p,primaryColor:t,fontSize:u}=r;return{fontSize:u,textColor:t,sizeTiny:a,sizeSmall:o,sizeMedium:i,sizeLarge:c,sizeHuge:p,color:t,opacitySpinning:d}}const ie={common:K,self:ae},le=$([$("@keyframes spin-rotate",`
 from {
 transform: rotate(0);
 }
 to {
 transform: rotate(360deg);
 }
 `),b("spin-container",`
 position: relative;
 `,[b("spin-body",`
 position: absolute;
 top: 50%;
 left: 50%;
 transform: translateX(-50%) translateY(-50%);
 `,[q()])]),b("spin-body",`
 display: inline-flex;
 align-items: center;
 justify-content: center;
 flex-direction: column;
 `),b("spin",`
 display: inline-flex;
 height: var(--n-size);
 width: var(--n-size);
 font-size: var(--n-size);
 color: var(--n-color);
 `,[O("rotate",`
 animation: spin-rotate 2s linear infinite;
 `)]),b("spin-description",`
 display: inline-block;
 font-size: var(--n-font-size);
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 margin-top: 8px;
 `),b("spin-content",`
 opacity: 1;
 transition: opacity .3s var(--n-bezier);
 pointer-events: all;
 `,[O("spinning",`
 user-select: none;
 -webkit-user-select: none;
 pointer-events: none;
 opacity: var(--n-opacity-spinning);
 `)])]),oe={small:20,medium:18,large:16},re=Object.assign(Object.assign(Object.assign({},V.props),{contentClass:String,contentStyle:[Object,String],description:String,size:{type:[String,Number],default:"medium"},show:{type:Boolean,default:!0},rotate:{type:Boolean,default:!0},spinning:{type:Boolean,validator:()=>!0,default:void 0},delay:Number}),J),ue=B({name:"Spin",props:re,slots:Object,setup(r){const{mergedClsPrefixRef:d,inlineThemeDisabled:a}=X(r),o=V("Spin","-spin",le,ie,r,d),i=N(()=>{const{size:u}=r,{common:{cubicBezierEaseInOut:l},self:f}=o.value,{opacitySpinning:j,color:P,textColor:L}=f,M=typeof u=="number"?Q(u):f[Y("size",u)];return{"--n-bezier":l,"--n-opacity-spinning":j,"--n-size":M,"--n-color":P,"--n-text-color":L}}),c=a?F("spin",N(()=>{const{size:u}=r;return typeof u=="number"?String(u):u[0]}),i,r):void 0,p=Z(r,["spinning","show"]),t=C(!1);return I(u=>{let l;if(p.value){const{delay:f}=r;if(f){l=window.setTimeout(()=>{t.value=!0},f),u(()=>{clearTimeout(l)});return}}t.value=p.value}),{mergedClsPrefix:d,active:t,mergedStrokeWidth:N(()=>{const{strokeWidth:u}=r;if(u!==void 0)return u;const{size:l}=r;return oe[typeof l=="number"?"medium":l]}),cssVars:a?void 0:i,themeClass:c==null?void 0:c.themeClass,onRender:c==null?void 0:c.onRender}},render(){var r,d;const{$slots:a,mergedClsPrefix:o,description:i}=this,c=a.icon&&this.rotate,p=(i||a.description)&&m("div",{class:`${o}-spin-description`},i||((r=a.description)===null||r===void 0?void 0:r.call(a))),t=a.icon?m("div",{class:[`${o}-spin-body`,this.themeClass]},m("div",{class:[`${o}-spin`,c&&`${o}-spin--rotate`],style:a.default?"":this.cssVars},a.icon()),p):m("div",{class:[`${o}-spin-body`,this.themeClass]},m(U,{clsPrefix:o,style:a.default?"":this.cssVars,stroke:this.stroke,"stroke-width":this.mergedStrokeWidth,radius:this.radius,scale:this.scale,class:`${o}-spin`}),p);return(d=this.onRender)===null||d===void 0||d.call(this),a.default?m("div",{class:[`${o}-spin-container`,this.themeClass],style:this.cssVars},m("div",{class:[`${o}-spin-content`,this.active&&`${o}-spin-content--spinning`,this.contentClass],style:this.contentStyle},a),m(E,{name:"fade-in-transition"},{default:()=>this.active?t:null})):t}}),de={xmlns:"http://www.w3.org/2000/svg","xmlns:xlink":"http://www.w3.org/1999/xlink",viewBox:"0 0 512 512"},R=B({name:"SearchOutline",render:function(d,a){return y(),A("svg",de,a[0]||(a[0]=[g("path",{d:"M221.09 64a157.09 157.09 0 1 0 157.09 157.09A157.1 157.1 0 0 0 221.09 64z",fill:"none",stroke:"currentColor","stroke-miterlimit":"10","stroke-width":"32"},null,-1),g("path",{fill:"none",stroke:"currentColor","stroke-linecap":"round","stroke-miterlimit":"10","stroke-width":"32",d:"M338.29 338.29L448 448"},null,-1)]))}}),ce={style:{"font-size":"13px","max-height":"500px",overflow:"auto",background:"var(--table-hover)",padding:"16px","border-radius":"8px",margin:"0"}},pe={style:{"margin-top":"8px"}},fe={style:{padding:"40px","text-align":"center"}},xe=B({__name:"Diagnose",setup(r){const d=H(),a=C(!1),o=C(""),i=C(null);async function c(){a.value=!0,o.value="",i.value=null;try{const p=await G.diagnose(d.current);i.value=p}catch(p){o.value=p.message}finally{a.value=!1}}return W(()=>{d.loadDatabases()}),(p,t)=>(y(),h(e(k),{vertical:"",size:16},{default:s(()=>{var u;return[n(e(v),null,{default:s(()=>[n(e(k),{align:"center",justify:"space-between"},{default:s(()=>[n(e(k),{align:"center"},{default:s(()=>[n(e(D),{size:"20",color:"#4F46E5"},{default:s(()=>[n(e(R))]),_:1}),n(e(_),{style:{"font-weight":"600","font-size":"16px"}},{default:s(()=>[...t[1]||(t[1]=[x("实时诊断",-1)])]),_:1})]),_:1}),n(e(k),{align:"center"},{default:s(()=>[n(e(_),null,{default:s(()=>[...t[2]||(t[2]=[x("数据库:",-1)])]),_:1}),n(e(te),{value:e(d).current,options:e(d).databases.map(l=>({label:l,value:l})),style:{width:"160px"},size:"small","onUpdate:value":t[0]||(t[0]=l=>e(d).setCurrent(l))},null,8,["value","options"]),n(e(ee),{type:"primary",size:"small",loading:a.value,onClick:c},{icon:s(()=>[n(e(D),null,{default:s(()=>[n(e(R))]),_:1})]),default:s(()=>[t[3]||(t[3]=x(" 开始诊断 ",-1))]),_:1},8,["loading"])]),_:1})]),_:1})]),_:1}),o.value?(y(),h(e(se),{key:0,type:"error",closable:""},{default:s(()=>[x(T(o.value),1)]),_:1})):z("",!0),(u=i.value)!=null&&u.data?(y(),h(e(ne),{key:1,cols:4,"x-gap":16,"y-gap":16,responsive:"screen","item-responsive":""},{default:s(()=>[n(e(S),{span:"4 m:1"},{default:s(()=>[n(e(v),null,{default:s(()=>[n(e(w),{label:"健康评分",value:i.value.data.score||i.value.data.health_score||"-"},{prefix:s(()=>[...t[4]||(t[4]=[g("span",{style:{"font-size":"24px"}},"🏥",-1)])]),_:1},8,["value"])]),_:1})]),_:1}),n(e(S),{span:"4 m:1"},{default:s(()=>[n(e(v),null,{default:s(()=>{var l,f;return[n(e(w),{label:"问题数",value:((l=i.value.data.issues)==null?void 0:l.length)||((f=i.value.data.warnings)==null?void 0:f.length)||0},null,8,["value"])]}),_:1})]),_:1}),n(e(S),{span:"4 m:1"},{default:s(()=>[n(e(v),null,{default:s(()=>{var l;return[n(e(w),{label:"慢查询",value:((l=i.value.data.slow_queries)==null?void 0:l.length)||0},null,8,["value"])]}),_:1})]),_:1}),n(e(S),{span:"4 m:1"},{default:s(()=>[n(e(v),null,{default:s(()=>{var l;return[n(e(w),{label:"锁等待",value:((l=i.value.data.locks)==null?void 0:l.length)||i.value.data.lock_waits||0},null,8,["value"])]}),_:1})]),_:1})]),_:1})):z("",!0),i.value?(y(),h(e(v),{key:2,title:"诊断数据"},{default:s(()=>[g("pre",ce,T(JSON.stringify(i.value,null,2)),1)]),_:1})):z("",!0),!i.value&&!a.value&&!o.value?(y(),h(e(v),{key:3,style:{"text-align":"center",padding:"60px"}},{default:s(()=>[t[7]||(t[7]=g("div",{style:{"font-size":"48px","margin-bottom":"16px"}},"🔍",-1)),n(e(_),{depth:"3",style:{"font-size":"16px"}},{default:s(()=>[...t[5]||(t[5]=[x('选择数据库并点击"开始诊断"',-1)])]),_:1}),g("div",pe,[n(e(_),{depth:"3"},{default:s(()=>[...t[6]||(t[6]=[x("将显示数据库实时健康状态",-1)])]),_:1})])]),_:1})):z("",!0),a.value?(y(),h(e(v),{key:4},{default:s(()=>[g("div",fe,[n(e(ue),{size:"large"}),t[8]||(t[8]=g("div",{style:{"margin-top":"12px",color:"var(--text-secondary)"}},"诊断中...",-1))])]),_:1})):z("",!0)]}),_:1}))}});export{xe as default};
