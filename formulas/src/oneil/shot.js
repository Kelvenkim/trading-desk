const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1280,height:900},deviceScaleFactor:2});
await p.goto('file://'+process.cwd()+'/oneil.html');await p.waitForTimeout(400);await p.screenshot({path:'oneil.png'});await b.close();})();
