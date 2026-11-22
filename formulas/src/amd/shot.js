const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1280,height:760},deviceScaleFactor:2});
await p.goto('file://'+process.cwd()+'/amd.html');await p.waitForTimeout(400);await p.screenshot({path:'amd.png'});await b.close();})();
