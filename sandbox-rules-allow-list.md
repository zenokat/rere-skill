## 娌欑洅鐧藉悕鍗曞懡浠ゅ鎵圭敵璇?
`sandbox-rules-allow-list.md` 鏄?鐢宠鍙拌处"锛屼笉鏄嚜鍔ㄧ敓鏁堢殑瑙勫垯鏂囦欢銆?鐪熸鐢熸晥鐨勯」鐩骇鐧藉悕鍗曚綅浜?`.codex/rules/revenue-rollup.rules`銆?涓轰簡璁╁懡浠ゅ墠缂€鑳借绋冲畾鍖归厤锛屽悓鏃堕伩鍏嶆妸铏氭嫙鐜璺緞銆乣PYTHONPATH` 鍜岀紪鐮佽缃暎钀藉埌姣忔潯鍛戒护閲岋紝鏈」鐩粺涓€閫氳繃 `.\.codex\scripts\rere.cmd` 浣滀负浠撳簱绾?CLI 鍚姩鍣ㄣ€?
### 绾跨▼鍐呬娇鐢ㄨ鍒?- 鍚庣画 Codex 绾跨▼鍦ㄥ噯澶囧彂璧?楂橀銆佷綆椋庨櫓銆佸彲澶嶇敤"鐨勬彁鏉冨墠锛屽繀椤诲厛妫€鏌ユ湰鏂囦欢銆?- 濡傛灉鍛戒护娌℃湁鐜版垚璁板綍锛屾垨鐜版湁璁板綍涓嶈冻浠ヨ鐩栧綋鍓嶅懡浠ゅ墠缂€锛屽繀椤诲厛琛ョ櫥璁帮紝鍐嶇敵璇锋湰娆℃彁鏉冿紱涓嶈鍙彁鏉冧笉鐣欑棔銆?- 鏂板鐢宠鏃讹紝鍛戒护鍓嶇紑瑕佸啓鎴?灏介噺闀裤€佷絾浠嶇ǔ瀹氬彲澶嶇敤"鐨勫叕鍏卞墠缂€锛岄伩鍏嶆妸涓存椂璺緞銆佸叿浣撳弬鏁板€兼垨涓€娆℃€т笂涓嬫枃鍐欒繘鍓嶇紑銆?- 鍙湁鏉冮檺绠＄悊鑰呮妸瑙勫垯鍔犲叆 `.codex/rules/*.rules` 鍚庯紝鎵嶇畻鐪熸瀹℃壒钀藉湴锛涙湰鏂囦欢涓殑"宸插鎵归€氳繃"鍙槸鍙拌处鐘舵€併€?
### 鐢宠鎸囧崡
- 鏂板琛ㄨ褰曟彁浜ゅ鎵逛箣鍓嶏紝搴斿厛check鏄惁宸叉湁鐩镐技鐨勫鎵癸紝濡傛灉瀛樺湪锛屽彲浠ュ鎵句笌鐩镐技瀹℃壒鐨勬渶闀垮叕鍏卞懡浠ゅ墠缂€锛屽苟鎻愪氦杩欎釜鍛戒护鐨勭櫧鍚嶅崟瀹℃壒銆?- 鏂板鐢宠鏃讹紝`宸插鎵归€氳繃` 瀛楁鐣欑┖锛涘鏋滄潈闄愮鐞嗚€呭皢鍛戒护鍔犲叆浜嗘矙绠辩櫧鍚嶅崟锛屽啀濉叆"鏄?銆?- **鏄庝护绂佹**鑷鍦ㄩ€氳繃娓呭崟涓姞鍏ユ寚浠わ紝涓€鍒囩敵璇烽兘蹇呴』涓斿彧鑳藉啓鍦ㄤ笅闈㈢殑琛ㄦ牸锛岀粡杩囧鏍稿悗鐢辨潈闄愮鐞嗗憳娣诲姞銆?

| 鐢宠鎿嶄綔 | 鎿嶄綔鐩殑 | 涓轰綍璁や负娌℃湁椋庨櫓 | 鍛戒护鍓嶇紑 | 宸插鎵归€氳繃 |
|---|---|---|---|---|
| `list_recog_items` | 璇诲彇椋炰功閰嶇疆搴撲腑鐨勭‘璁ら」鐩洰褰曪紝渚涢€夋嫨 `recog_id` | 鍙鐩綍淇℃伅锛屼笉鍐欒繙绔暟鎹?| `.\.codex\scripts\rere.cmd list_recog_items` | 鏄?|
| `run_recog_rollup --validate/--preview/--upload` | 缁熶竴鎵ц缁撴瀯鏍￠獙銆乸review 鐢熸垚涓庡奖瀛愯〃涓婁紶 | 閫氳繃浠撳簱绾у惎鍔ㄥ櫒瑙﹀彂鍚屼竴鏉＄櫧鍚嶅崟瑙勫垯锛涘叿浣撴槸鍚﹁杩滅銆佸啓鏈湴鎴栧啓褰卞瓙琛紝鐢卞悗缁笟鍔″弬鏁板喅瀹氾紝杈圭晫娓呮櫚 | `.\.codex\scripts\rere.cmd run_recog_rollup <mode> ...` | 鏄?|
| `Invoke-WebRequest codebuddy docs` | 鍙鎶撳彇 CodeBuddy 瀹樻柟鏂囨。椤甸潰锛岀敤浜庢牳瀵?CLI 濂戠害銆佹棤澶存ā寮忋€佽緭鍑烘牸寮忎笌瑙傛祴鑳藉姏 | 閫氳繃鍥哄畾鑴氭湰闄愬埗涓?`https://www.codebuddy.ai/docs/` 涓嬬殑鍙椤甸潰鎶撳彇锛屼笉鍐欐湰鍦板伐浣滃尯澶栫姸鎬侊紝涓嶈Е鍙戜换浣曡繙绔啓鍏?| `powershell.exe -File .\.codex\scripts\fetch_codebuddy_docs.ps1 <docs-url-or-path>` | 鏄?|
| `codebuddy headless eval` | 閫氳繃 CodeBuddy 瀹樻柟鏃犲ご妯″紡杩愯鍗曟潯璇勬祴 prompt锛屼緵 WorkBuddy / CodeBuddy 鍚屾牳璇勬祴閲囬泦妯″瀷鍝嶅簲 | 鍛戒护鍏ュ彛鍥哄畾涓哄畼鏂?`-p/--print` 鏃犲ご妯″紡锛涜瘎娴?prompt 鐢?harness 鐢熸垚锛岄粯璁ゅ彧璇伙紝涓嶆墽琛?upload 鎴栧閮ㄥ啓鍔ㄤ綔锛涜緭鍑虹敤浜庢湰鍦拌瘉鎹寘涓庤瘎鍒?| `codebuddy -p <prompt> ...` | 鏄?|
| `cbc headless eval` | 浣跨敤 CodeBuddy CLI 鍒悕杩愯鍚屼竴绫绘棤澶磋瘎娴?prompt锛屼綔涓?`codebuddy` 浜岃繘鍒朵笉鍙敤鏃剁殑绛変环鍏ュ彛 | `cbc` 鏄畼鏂?CLI 鍒悕锛涚敤閫斻€佹潈闄愯竟鐣屽拰 `codebuddy -p` 涓€鑷达紝榛樿鍙骞剁敱 harness 璁板綍鍛戒护涓庤緭鍑?| `cbc -p <prompt> ...` |  |
| `run_skill_eval_batch` | 閫氳繃浠撳簱绾?harness 鍏ュ彛鍙戣捣 WorkBuddy / CodeBuddy 鍚屾牳璇勬祴鎵规锛岃嚜鍔ㄦ敹闆?evidence 涓?scorecard | 鍏ュ彛鍥哄畾涓烘湰浠撳簱璇勬祴搴曞骇锛涚湡瀹炲閮ㄥ姩浣滀粛鐢?case 瀹夊叏澹版槑銆佸啓绛栫暐鍜?CodeBuddy 鏉冮檺妯″紡鎺у埗锛岄粯璁ゅ彧璇?| `.\.codex\scripts\rere.cmd run_skill_eval_batch ...` | 鏄?|
| `docker version` | 读取本机 Docker daemon 版本，确认 eval container sandbox 运行时可用 | 只读本机 Docker 版本信息，不创建容器、不修改镜像、不写远端 | `docker version ...` | 是 |

