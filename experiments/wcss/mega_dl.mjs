// Download a public MEGA file link (e.g. DANE.zip) with megajs. MEGA's bandwidth quota is per source IP, so running
// this on the WCSS login node works while this PC's quota is exhausted.
// Setup on WCSS (once): official Node binary in $RP_PD/redpill/tools/node-v24.11.0-linux-x64, `npm install megajs@1`.
// Usage: node mega_dl.mjs '<mega url with #key>' <out.zip>
import { File } from 'megajs'
import fs from 'node:fs'

const [url, out] = process.argv.slice(2)
const f = File.fromURL(url)
await f.loadAttributes()
console.log('name', f.name, 'size', f.size)
const ws = fs.createWriteStream(out)
const st = f.download()
let got = 0, last = 0
st.on('data', c => { got += c.length; if (got - last > 25e6) { last = got; console.log(new Date().toISOString(), (got / 1e6).toFixed(0), 'MB') } })
st.on('error', e => { console.error('ERR', e.message); process.exit(2) })
st.pipe(ws)
ws.on('finish', () => console.log('DONE', got))
