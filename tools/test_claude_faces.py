"""Compare real generated C++ and JS renderers pixel for pixel, including blinks."""
from pathlib import Path
import json
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent.parent
TIMES=[0,1.25,2.35,5.7,9.2]


def main():
    data=json.loads((ROOT/'expressions/claude_pixel.json').read_text())
    cases=[dict(name=name,screen=face['screen'],t=t) for name,face in data['faces'].items() for t in TIMES]
    calls=[]
    for case in cases:
        s=case['screen'];rgb=int(s['fg'][1:],16)
        color=((rgb>>16&248)<<8)|((rgb>>8&252)<<3)|((rgb&255)>>3)
        calls.append('c.clear();drawClaudeEyes(c,"%s","%s",%d,%sf);drawClaudeAccent(c,"%s",%d);c.write();' % (s['pose'],s['anim'],color,float(case['t']),s['extra'],color))
    cpp='''#include <cstdint>
#include <string>
#include <cmath>
#include <cstring>
#include <iostream>
using String=std::string;
class GFXcanvas16 {
  uint16_t pixels[240*240]{};
public:
  void clear(){std::memset(pixels,0,sizeof(pixels));}
  void fillRect(int x,int y,int w,int h,uint16_t color){
    for(int row=y;row<y+h;row++)for(int col=x;col<x+w;col++)
      if(row>=0&&row<240&&col>=0&&col<240)pixels[row*240+col]=color;
  }
  void write(){std::cout.write((char*)pixels,sizeof(pixels));}
};
#include "claude_faces.generated.h"
int main(){GFXcanvas16 c;__CALLS__}
'''.replace('__CALLS__','\n'.join(calls))
    js=(ROOT/'bridge/claude_faces.js').read_text()+'''
const cases=__CASES__;
for(const c of cases){
 const pixels=Buffer.alloc(240*240*2);
 const ctx={fillStyle:'#000000',fillRect(x,y,w,h){
  const rgb=parseInt(this.fillStyle.slice(1),16),color=((rgb>>>16&248)<<8)|((rgb>>>8&252)<<3)|((rgb&255)>>>3);
  for(let row=y;row<y+h;row++)for(let col=x;col<x+w;col++)
   if(row>=0&&row<240&&col>=0&&col<240)pixels.writeUInt16LE(color,(row*240+col)*2);
 }};
 drawClaudeFace(ctx,c.screen,c.t);process.stdout.write(pixels);
}
'''.replace('__CASES__',json.dumps(cases))
    with tempfile.TemporaryDirectory(prefix='agentpet-faces-') as folder:
        temp=Path(folder);(temp/'test.cpp').write_text(cpp);(temp/'test.js').write_text(js)
        subprocess.run(['c++','-std=c++11','-I',str(ROOT/'firmware/src'),str(temp/'test.cpp'),'-o',str(temp/'test')],check=True,capture_output=True)
        device=subprocess.run([str(temp/'test')],check=True,capture_output=True).stdout
        browser=subprocess.run(['node',str(temp/'test.js')],check=True,capture_output=True).stdout
        stride=240*240*2
        assert len(device)==len(browser)==len(cases)*stride
        for i,case in enumerate(cases):
            assert device[i*stride:(i+1)*stride]==browser[i*stride:(i+1)*stride],case
    print(f'PASS: {len(cases)} firmware/browser frames match pixel for pixel across {len(data["faces"])} faces.')


if __name__=='__main__':
    main()
