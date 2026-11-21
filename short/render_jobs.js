// one browser for all overlay jobs. usage: node render_jobs.js jobs.json
// job: {html, dir, fps, isec, st, outAt, osec, clip:{x,y,width,height}}  -> dir/static.png, dir/in/%04d.png, dir/out/%04d.png
const {chromium}=require('playwright');const fs=require('fs');
(async()=>{
 const jobs=JSON.parse(fs.readFileSync(process.argv[2]));
 const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
 for(const j of jobs){
  await p.goto('file://'+j.html);await p.waitForSelector('body[data-ready]');
  const seek=t=>p.evaluate(t=>{document.getAnimations().forEach(a=>{a.pause();a.currentTime=t});window.__tick&&window.__tick(t)},t);
  const shot=path=>p.screenshot({path,clip:j.clip,omitBackground:true});
  fs.mkdirSync(j.dir+'/in',{recursive:true});fs.mkdirSync(j.dir+'/out',{recursive:true});
  await seek(j.st*1000);await shot(j.dir+'/static.png');
  for(let i=0;i<Math.round(j.fps*j.isec);i++){await seek(i*1000/j.fps);await shot(`${j.dir}/in/${String(i).padStart(4,'0')}.png`);}
  for(let i=0;i<Math.round(j.fps*j.osec);i++){await seek(j.outAt*1000+i*1000/j.fps);await shot(`${j.dir}/out/${String(i).padStart(4,'0')}.png`);}
 }
 await b.close();
})();
