import{d as C,h as s,c as L,S as ee,R as te,i as re,F as V,k as S,l as _,D as m,u as oe,o as ne,G as w,p as l,m as a,q as r,x as h,y as le,K as T,r as ie,A as R,B as ae}from"./index-DzV7P-Cc.js";import{d as H,G as j,h as b,f as u,i as y,g,D as se,E as de,m as F,x as W,n as O,y as K,e as ce,_ as ue,a1 as $,R as E,a2 as D,a3 as z,Q as I,a4 as ve}from"./text-DJ5v9n0F.js";import{R as fe}from"./ReloadOutline-eUsqSfRF.js";import{N as ge}from"./Alert-DA7lj8Yb.js";import{o as he}from"./Select-WRznkyhc.js";function me(t){const{textColor2:e,cardColor:i,modalColor:d,popoverColor:v,dividerColor:x,borderRadius:p,fontSize:f,hoverColor:c}=t;return{textColor:e,color:i,colorHover:c,colorModal:d,colorHoverModal:j(d,c),colorPopover:v,colorHoverPopover:j(v,c),borderColor:x,borderColorModal:j(d,x),borderColorPopover:j(v,x),borderRadius:p,fontSize:f}}const xe={common:H,self:me};function pe(t){const{textColor1:e,textColor2:i,fontWeightStrong:d,fontSize:v}=t;return{fontSize:v,titleTextColor:e,textColor:i,titleFontWeight:d}}const be={common:H,self:pe},we=b([u("list",`
 --n-merged-border-color: var(--n-border-color);
 --n-merged-color: var(--n-color);
 --n-merged-color-hover: var(--n-color-hover);
 margin: 0;
 font-size: var(--n-font-size);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 padding: 0;
 list-style-type: none;
 color: var(--n-text-color);
 background-color: var(--n-merged-color);
 `,[y("show-divider",[u("list-item",[b("&:not(:last-child)",[g("divider",`
 background-color: var(--n-merged-border-color);
 `)])])]),y("clickable",[u("list-item",`
 cursor: pointer;
 `)]),y("bordered",`
 border: 1px solid var(--n-merged-border-color);
 border-radius: var(--n-border-radius);
 `),y("hoverable",[u("list-item",`
 border-radius: var(--n-border-radius);
 `,[b("&:hover",`
 background-color: var(--n-merged-color-hover);
 `,[g("divider",`
 background-color: transparent;
 `)])])]),y("bordered, hoverable",[u("list-item",`
 padding: 12px 20px;
 `),g("header, footer",`
 padding: 12px 20px;
 `)]),g("header, footer",`
 padding: 12px 0;
 box-sizing: border-box;
 transition: border-color .3s var(--n-bezier);
 `,[b("&:not(:last-child)",`
 border-bottom: 1px solid var(--n-merged-border-color);
 `)]),u("list-item",`
 position: relative;
 padding: 12px 0; 
 box-sizing: border-box;
 display: flex;
 flex-wrap: nowrap;
 align-items: center;
 transition:
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[g("prefix",`
 margin-right: 20px;
 flex: 0;
 `),g("suffix",`
 margin-left: 20px;
 flex: 0;
 `),g("main",`
 flex: 1;
 `),g("divider",`
 height: 1px;
 position: absolute;
 bottom: 0;
 left: 0;
 right: 0;
 background-color: transparent;
 transition: background-color .3s var(--n-bezier);
 pointer-events: none;
 `)])]),se(u("list",`
 --n-merged-color-hover: var(--n-color-hover-modal);
 --n-merged-color: var(--n-color-modal);
 --n-merged-border-color: var(--n-border-color-modal);
 `)),de(u("list",`
 --n-merged-color-hover: var(--n-color-hover-popover);
 --n-merged-color: var(--n-color-popover);
 --n-merged-border-color: var(--n-border-color-popover);
 `))]),Ce=Object.assign(Object.assign({},O.props),{size:{type:String,default:"medium"},bordered:Boolean,clickable:Boolean,hoverable:Boolean,showDivider:{type:Boolean,default:!0}}),U=ce("n-list"),A=C({name:"List",props:Ce,slots:Object,setup(t){const{mergedClsPrefixRef:e,inlineThemeDisabled:i,mergedRtlRef:d}=F(t),v=W("List",d,e),x=O("List","-list",we,xe,t,e);ee(U,{showDividerRef:te(t,"showDivider"),mergedClsPrefixRef:e});const p=L(()=>{const{common:{cubicBezierEaseInOut:c},self:{fontSize:o,textColor:n,color:k,colorModal:M,colorPopover:N,borderColor:G,borderColorModal:q,borderColorPopover:Q,borderRadius:J,colorHover:X,colorHoverModal:Y,colorHoverPopover:Z}}=x.value;return{"--n-font-size":o,"--n-bezier":c,"--n-text-color":n,"--n-color":k,"--n-border-radius":J,"--n-border-color":G,"--n-border-color-modal":q,"--n-border-color-popover":Q,"--n-color-modal":M,"--n-color-popover":N,"--n-color-hover":X,"--n-color-hover-modal":Y,"--n-color-hover-popover":Z}}),f=i?K("list",void 0,p,t):void 0;return{mergedClsPrefix:e,rtlEnabled:v,cssVars:i?void 0:p,themeClass:f==null?void 0:f.themeClass,onRender:f==null?void 0:f.onRender}},render(){var t;const{$slots:e,mergedClsPrefix:i,onRender:d}=this;return d==null||d(),s("ul",{class:[`${i}-list`,this.rtlEnabled&&`${i}-list--rtl`,this.bordered&&`${i}-list--bordered`,this.showDivider&&`${i}-list--show-divider`,this.hoverable&&`${i}-list--hoverable`,this.clickable&&`${i}-list--clickable`,this.themeClass],style:this.cssVars},e.header?s("div",{class:`${i}-list__header`},e.header()):null,(t=e.default)===null||t===void 0?void 0:t.call(e),e.footer?s("div",{class:`${i}-list__footer`},e.footer()):null)}}),P=C({name:"ListItem",slots:Object,setup(){const t=re(U,null);return t||ue("list-item","`n-list-item` must be placed in `n-list`."),{showDivider:t.showDividerRef,mergedClsPrefix:t.mergedClsPrefixRef}},render(){const{$slots:t,mergedClsPrefix:e}=this;return s("li",{class:`${e}-list-item`},t.prefix?s("div",{class:`${e}-list-item__prefix`},t.prefix()):null,t.default?s("div",{class:`${e}-list-item__main`},t):null,t.suffix?s("div",{class:`${e}-list-item__suffix`},t.suffix()):null,this.showDivider&&s("div",{class:`${e}-list-item__divider`}))}}),ke=u("thing",`
 display: flex;
 transition: color .3s var(--n-bezier);
 font-size: var(--n-font-size);
 color: var(--n-text-color);
`,[u("thing-avatar",`
 margin-right: 12px;
 margin-top: 2px;
 `),u("thing-avatar-header-wrapper",`
 display: flex;
 flex-wrap: nowrap;
 `,[u("thing-header-wrapper",`
 flex: 1;
 `)]),u("thing-main",`
 flex-grow: 1;
 `,[u("thing-header",`
 display: flex;
 margin-bottom: 4px;
 justify-content: space-between;
 align-items: center;
 `,[g("title",`
 font-size: 16px;
 font-weight: var(--n-title-font-weight);
 transition: color .3s var(--n-bezier);
 color: var(--n-title-text-color);
 `)]),g("description",[b("&:not(:last-child)",`
 margin-bottom: 4px;
 `)]),g("content",[b("&:not(:first-child)",`
 margin-top: 12px;
 `)]),g("footer",[b("&:not(:first-child)",`
 margin-top: 12px;
 `)]),g("action",[b("&:not(:first-child)",`
 margin-top: 12px;
 `)])])]),_e=Object.assign(Object.assign({},O.props),{title:String,titleExtra:String,description:String,descriptionClass:String,descriptionStyle:[String,Object],content:String,contentClass:String,contentStyle:[String,Object],contentIndented:Boolean}),B=C({name:"Thing",props:_e,slots:Object,setup(t,{slots:e}){const{mergedClsPrefixRef:i,inlineThemeDisabled:d,mergedRtlRef:v}=F(t),x=O("Thing","-thing",ke,be,t,i),p=W("Thing",v,i),f=L(()=>{const{self:{titleTextColor:o,textColor:n,titleFontWeight:k,fontSize:M},common:{cubicBezierEaseInOut:N}}=x.value;return{"--n-bezier":N,"--n-font-size":M,"--n-text-color":n,"--n-title-font-weight":k,"--n-title-text-color":o}}),c=d?K("thing",void 0,f,t):void 0;return()=>{var o;const{value:n}=i,k=p?p.value:!1;return(o=c==null?void 0:c.onRender)===null||o===void 0||o.call(c),s("div",{class:[`${n}-thing`,c==null?void 0:c.themeClass,k&&`${n}-thing--rtl`],style:d?void 0:f.value},e.avatar&&t.contentIndented?s("div",{class:`${n}-thing-avatar`},e.avatar()):null,s("div",{class:`${n}-thing-main`},!t.contentIndented&&(e.header||t.title||e["header-extra"]||t.titleExtra||e.avatar)?s("div",{class:`${n}-thing-avatar-header-wrapper`},e.avatar?s("div",{class:`${n}-thing-avatar`},e.avatar()):null,e.header||t.title||e["header-extra"]||t.titleExtra?s("div",{class:`${n}-thing-header-wrapper`},s("div",{class:`${n}-thing-header`},e.header||t.title?s("div",{class:`${n}-thing-header__title`},e.header?e.header():t.title):null,e["header-extra"]||t.titleExtra?s("div",{class:`${n}-thing-header__extra`},e["header-extra"]?e["header-extra"]():t.titleExtra):null),e.description||t.description?s("div",{class:[`${n}-thing-main__description`,t.descriptionClass],style:t.descriptionStyle},e.description?e.description():t.description):null):null):s(V,null,e.header||t.title||e["header-extra"]||t.titleExtra?s("div",{class:`${n}-thing-header`},e.header||t.title?s("div",{class:`${n}-thing-header__title`},e.header?e.header():t.title):null,e["header-extra"]||t.titleExtra?s("div",{class:`${n}-thing-header__extra`},e["header-extra"]?e["header-extra"]():t.titleExtra):null):null,e.description||t.description?s("div",{class:[`${n}-thing-main__description`,t.descriptionClass],style:t.descriptionStyle},e.description?e.description():t.description):null),e.default||t.content?s("div",{class:[`${n}-thing-main__content`,t.contentClass],style:t.contentStyle},e.default?e.default():t.content):null,e.footer?s("div",{class:`${n}-thing-main__footer`},e.footer()):null,e.action?s("div",{class:`${n}-thing-main__action`},e.action()):null))}}}),ye={xmlns:"http://www.w3.org/2000/svg","xmlns:xlink":"http://www.w3.org/1999/xlink",viewBox:"0 0 512 512"},$e=C({name:"BookOutline",render:function(e,i){return m(),S("svg",ye,i[0]||(i[0]=[_("path",{d:"M256 160c16-63.16 76.43-95.41 208-96a15.94 15.94 0 0 1 16 16v288a16 16 0 0 1-16 16c-128 0-177.45 25.81-208 64c-30.37-38-80-64-208-64c-9.88 0-16-8.05-16-17.93V80a15.94 15.94 0 0 1 16-16c131.57.59 192 32.84 208 96z",fill:"none",stroke:"currentColor","stroke-linecap":"round","stroke-linejoin":"round","stroke-width":"32"},null,-1),_("path",{fill:"none",stroke:"currentColor","stroke-linecap":"round","stroke-linejoin":"round","stroke-width":"32",d:"M256 160v288"},null,-1)]))}}),ze={xmlns:"http://www.w3.org/2000/svg","xmlns:xlink":"http://www.w3.org/1999/xlink",viewBox:"0 0 512 512"},Se=C({name:"CodeSlashOutline",render:function(e,i){return m(),S("svg",ze,i[0]||(i[0]=[_("path",{fill:"none",stroke:"currentColor","stroke-linecap":"round","stroke-linejoin":"round","stroke-width":"32",d:"M160 368L32 256l128-112"},null,-1),_("path",{fill:"none",stroke:"currentColor","stroke-linecap":"round","stroke-linejoin":"round","stroke-width":"32",d:"M352 368l128-112l-128-112"},null,-1),_("path",{fill:"none",stroke:"currentColor","stroke-linecap":"round","stroke-linejoin":"round","stroke-width":"32",d:"M304 96l-96 320"},null,-1)]))}}),Re={xmlns:"http://www.w3.org/2000/svg","xmlns:xlink":"http://www.w3.org/1999/xlink",viewBox:"0 0 512 512"},je=C({name:"SettingsOutline",render:function(e,i){return m(),S("svg",Re,i[0]||(i[0]=[_("path",{d:"M262.29 192.31a64 64 0 1 0 57.4 57.4a64.13 64.13 0 0 0-57.4-57.4zM416.39 256a154.34 154.34 0 0 1-1.53 20.79l45.21 35.46a10.81 10.81 0 0 1 2.45 13.75l-42.77 74a10.81 10.81 0 0 1-13.14 4.59l-44.9-18.08a16.11 16.11 0 0 0-15.17 1.75A164.48 164.48 0 0 1 325 400.8a15.94 15.94 0 0 0-8.82 12.14l-6.73 47.89a11.08 11.08 0 0 1-10.68 9.17h-85.54a11.11 11.11 0 0 1-10.69-8.87l-6.72-47.82a16.07 16.07 0 0 0-9-12.22a155.3 155.3 0 0 1-21.46-12.57a16 16 0 0 0-15.11-1.71l-44.89 18.07a10.81 10.81 0 0 1-13.14-4.58l-42.77-74a10.8 10.8 0 0 1 2.45-13.75l38.21-30a16.05 16.05 0 0 0 6-14.08c-.36-4.17-.58-8.33-.58-12.5s.21-8.27.58-12.35a16 16 0 0 0-6.07-13.94l-38.19-30A10.81 10.81 0 0 1 49.48 186l42.77-74a10.81 10.81 0 0 1 13.14-4.59l44.9 18.08a16.11 16.11 0 0 0 15.17-1.75A164.48 164.48 0 0 1 187 111.2a15.94 15.94 0 0 0 8.82-12.14l6.73-47.89A11.08 11.08 0 0 1 213.23 42h85.54a11.11 11.11 0 0 1 10.69 8.87l6.72 47.82a16.07 16.07 0 0 0 9 12.22a155.3 155.3 0 0 1 21.46 12.57a16 16 0 0 0 15.11 1.71l44.89-18.07a10.81 10.81 0 0 1 13.14 4.58l42.77 74a10.8 10.8 0 0 1-2.45 13.75l-38.21 30a16.05 16.05 0 0 0-6.05 14.08c.33 4.14.55 8.3.55 12.47z",fill:"none",stroke:"currentColor","stroke-linecap":"round","stroke-linejoin":"round","stroke-width":"32"},null,-1)]))}}),Ee={key:1,style:{padding:"20px","text-align":"center",color:"var(--text-secondary)"}},De=C({__name:"Configuration",setup(t){const e=oe(),i=R(null),d=R(null),v=R(!1),x=R(!1);async function p(){x.value=!0;try{i.value=await ae.status(),await e.loadDatabases()}catch{}finally{x.value=!1}}async function f(){v.value=!0,d.value=null;try{const o=await(await fetch(`/api/diagnose/connection?database=${encodeURIComponent(e.current)}`)).json();d.value={success:o.success,message:o.message||(o.success?"连接成功":"连接失败：无法连接到数据库")},o.success?console.log("SUCCESS:","连接成功"):console.warn("WARN:","连接失败")}catch(c){d.value={success:!1,message:`请求失败: ${c.message}`}}finally{v.value=!1}}return ne(p),(c,o)=>(m(),w(r($),{vertical:"",size:16},{default:l(()=>[a(r(z),null,{default:l(()=>[a(r($),{align:"center"},{default:l(()=>[a(r(E),{size:"20",color:"#4F46E5"},{default:l(()=>[a(r(je))]),_:1}),a(r(D),{style:{"font-weight":"600","font-size":"16px"}},{default:l(()=>[...o[1]||(o[1]=[h("系统配置",-1)])]),_:1})]),_:1})]),_:1}),a(r(z),{title:"API 服务状态"},{default:l(()=>[i.value?(m(),w(r(A),{key:0},{default:l(()=>[a(r(P),null,{prefix:l(()=>[...o[2]||(o[2]=[h("🟢",-1)])]),default:l(()=>[a(r(B),{title:"服务状态",description:"运行中"})]),_:1}),a(r(P),null,{prefix:l(()=>[...o[3]||(o[3]=[h("📦",-1)])]),default:l(()=>[a(r(B),{title:"版本",description:"v"+i.value.version},null,8,["description"])]),_:1}),a(r(P),null,{prefix:l(()=>[...o[4]||(o[4]=[h("🔗",-1)])]),default:l(()=>{var n;return[a(r(B),{title:"API 端点",description:((n=i.value.api_endpoints)==null?void 0:n.length)+" 个"},null,8,["description"])]}),_:1})]),_:1})):(m(),S("div",Ee,"加载中..."))]),_:1}),a(r(z),{title:"🔌 数据库连接测试"},{default:l(()=>[a(r($),{vertical:"",size:12},{default:l(()=>[a(r(D),{depth:"3"},{default:l(()=>[...o[5]||(o[5]=[h("选择一个数据库别名，测试是否能正常连接。",-1)])]),_:1}),a(r($),{align:"center"},{default:l(()=>[a(r(he),{value:r(e).current,options:r(e).databases.map(n=>({label:n,value:n})),style:{width:"300px"},size:"small","onUpdate:value":o[0]||(o[0]=n=>r(e).setCurrent(n))},null,8,["value","options"]),a(r(I),{type:"primary",size:"small",loading:v.value,onClick:f},{icon:l(()=>[a(r(E),null,{default:l(()=>[a(r(fe))]),_:1})]),default:l(()=>[o[6]||(o[6]=h(" 测试连接 ",-1))]),_:1},8,["loading"])]),_:1}),d.value?(m(),w(r(ge),{key:0,type:d.value.success?"success":"error",closable:""},{default:l(()=>[h(le(d.value.message),1)]),_:1},8,["type"])):T("",!0)]),_:1})]),_:1}),a(r(z),{title:"📋 已配置数据库"},{default:l(()=>[r(e).databases.length?(m(),w(r(A),{key:0},{default:l(()=>[(m(!0),S(V,null,ie(r(e).databases,n=>(m(),w(r(P),{key:n,onClick:k=>r(e).setCurrent(n),style:{cursor:"pointer"}},{prefix:l(()=>[...o[7]||(o[7]=[h("🗄️",-1)])]),suffix:l(()=>[n===r(e).current?(m(),w(r(ve),{key:0,type:"primary",size:"small"},{default:l(()=>[...o[8]||(o[8]=[h("当前",-1)])]),_:1})):T("",!0)]),default:l(()=>[a(r(B),{title:n,description:n===r(e).current?"当前选中":"点击切换"},null,8,["title","description"])]),_:2},1032,["onClick"]))),128))]),_:1})):(m(),w(r(D),{key:1,depth:"3"},{default:l(()=>[...o[9]||(o[9]=[h("暂无已配置的数据库",-1)])]),_:1}))]),_:1}),a(r(z),{title:"快速链接"},{default:l(()=>[a(r($),null,{default:l(()=>[a(r(I),{tag:"a",href:"/docs",target:"_blank",ghost:""},{icon:l(()=>[a(r(E),null,{default:l(()=>[a(r(Se))]),_:1})]),default:l(()=>[o[10]||(o[10]=h(" Swagger API 文档 ",-1))]),_:1}),a(r(I),{tag:"a",href:"/redoc",target:"_blank",ghost:""},{icon:l(()=>[a(r(E),null,{default:l(()=>[a(r($e))]),_:1})]),default:l(()=>[o[11]||(o[11]=h(" ReDoc 文档 ",-1))]),_:1})]),_:1})]),_:1})]),_:1}))}});export{De as default};
