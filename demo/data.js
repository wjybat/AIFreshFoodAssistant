/* ============================================================
   共享数据：场景 + 菜谱
   index.html 与 recipe.html 共用
   ============================================================ */
const SCENARIOS = {
  s1: {
    name:'雨天晚餐', icon:'🌧️',
    date:'2026-07-08 周三',
    weather:{icon:'🌧️',text:'小雨 18°C',desc:'体感偏凉·热菜需求上升'},
    situation:{
      inventory:[
        {name:'青椒',stock:'50kg',level:65,days:'1天临期',status:'danger'},
        {name:'猪肉(丝)',stock:'80kg',level:90,days:'库存偏高',status:'warn'},
        {name:'豆腐',stock:'30kg',level:55,days:'2天临期',status:'danger'},
        {name:'熟食米饭',stock:'120份',level:70,days:'今日销量-40%',status:'warn'},
        {name:'鸡蛋',stock:'200盒',level:40,days:'正常',status:'ok'},
        {name:'紫菜',stock:'60包',level:30,days:'正常',status:'ok'},
      ],
      community:{type:'家庭客群为主',radius:'3km',peak:'18:00 下班高峰',office:'周边2栋写字楼',kids:'学区房占比35%'},
      flow:'预计 850 人',
      hot:'青椒肉丝 · 麻婆豆腐 · 番茄炒蛋'
    },
    reasoning:[
      {tag:'danger',tagText:'临期',text:'检测到 <b>青椒</b> 仅剩 1 天临期 + <b>猪肉</b> 库存偏高 <span class="arrow">→</span> 匹配菜谱 <b>青椒肉丝</b>'},
      {tag:'danger',tagText:'临期',text:'检测到 <b>豆腐</b> 2 天临期 <span class="arrow">→</span> 匹配菜谱 <b>麻婆豆腐</b>'},
      {tag:'info',tagText:'场景',text:'雨天体感凉 <b>热菜需求↑</b> + 米饭熟食销量降 <span class="arrow">→</span> 联动熟食区出 <b>米饭+例汤</b>'},
      {tag:'ok',tagText:'客群',text:'家庭客群 + 18:00 下班高峰 <span class="arrow">→</span> 推荐 <b>2 人份备菜包</b>，17:30 精准推送'},
      {tag:'warn',tagText:'组合',text:'组合优化：青椒肉丝(主)+麻婆豆腐(配)+紫菜蛋花汤+熟食米饭 <span class="arrow">→</span> 品类均衡·毛利达标'},
    ],
    menu:[
      {name:'青椒肉丝',emoji:'🫑',role:'主菜',roleColor:'var(--warm)',badge:'今日主推',badgeColor:'#f97316',bg:'linear-gradient(135deg,#dcfce7,#bbf7d0)',
       desc:'15分钟快手菜·下饭神器',ingr:[{n:'青椒',c:'urgent'},{n:'猪肉丝',c:'high'},{n:'蒜',c:''},{n:'酱油',c:''}],
       recipe:{
         servings:'2人份',time:'15分钟',difficulty:'简单',calories:'约320千卡',
         ingredients:[
           {name:'青椒',amount:'200g',note:'切丝'},
           {name:'猪肉丝',amount:'300g',note:'提前腌制'},
           {name:'蒜',amount:'3瓣',note:'切末'},
           {name:'生抽',amount:'2勺'},
           {name:'料酒',amount:'1勺'},
           {name:'淀粉',amount:'1勺'},
           {name:'盐',amount:'适量'},
           {name:'食用油',amount:'2勺'},
         ],
         steps:[
           '猪肉丝加生抽、料酒、淀粉抓匀，腌制10分钟',
           '青椒去籽去蒂，切成细丝',
           '热锅冷油，下肉丝滑散至变色，盛出备用',
           '锅中余油爆香蒜末，下青椒丝大火翻炒1分钟',
           '肉丝回锅，加生抽、盐快速翻炒均匀',
           '出锅装盘，趁热食用',
         ],
         tips:'大火快炒保持青椒脆嫩；肉丝提前腌制更嫩滑；青椒丝不要炒太久以免变软塌。'
       }},
      {name:'麻婆豆腐',emoji:'🌶️',role:'配菜',roleColor:'var(--red)',badge:'清临期',badgeColor:'#ef4444',bg:'linear-gradient(135deg,#fee2e2,#fecaca)',
       desc:'麻辣鲜香·配饭一绝',ingr:[{n:'豆腐',c:'urgent'},{n:'猪肉末',c:'high'},{n:'豆瓣酱',c:''}],
       recipe:{
         servings:'2人份',time:'10分钟',difficulty:'简单',calories:'约280千卡',
         ingredients:[
           {name:'嫩豆腐',amount:'1块(约400g)',note:'切2cm方块'},
           {name:'猪肉末',amount:'100g'},
           {name:'郫县豆瓣酱',amount:'1.5勺',note:'剁碎'},
           {name:'花椒粉',amount:'1勺'},
           {name:'蒜末',amount:'2瓣'},
           {name:'葱花',amount:'适量'},
           {name:'生抽',amount:'1勺'},
           {name:'淀粉水',amount:'2勺'},
           {name:'食用油',amount:'2勺'},
         ],
         steps:[
           '豆腐切2cm方块，开水焯水1分钟，沥干备用',
           '热锅下油，炒散猪肉末至变色',
           '加豆瓣酱、蒜末小火炒出红油',
           '加半碗清水烧开，放入豆腐块',
           '小火煮3分钟让豆腐入味',
           '淋淀粉水勾芡，轻轻推匀（不要大力翻炒）',
           '撒花椒粉、葱花，出锅装盘',
         ],
         tips:'豆腐先焯水不易碎；勾芡可分两次淋更均匀；郫县豆瓣酱本身咸，少放盐。'
       }},
      {name:'紫菜蛋花汤',emoji:'🍵',role:'汤品',roleColor:'var(--blue)',badge:'联动',badgeColor:'#3b82f6',bg:'linear-gradient(135deg,#dbeafe,#bfdbfe)',
       desc:'3分钟出锅·暖胃解腻',ingr:[{n:'紫菜',c:''},{n:'鸡蛋',c:''}],
       recipe:{
         servings:'2人份',time:'5分钟',difficulty:'简单',calories:'约80千卡',
         ingredients:[
           {name:'干紫菜',amount:'1小把(约5g)'},
           {name:'鸡蛋',amount:'2个'},
           {name:'葱花',amount:'适量'},
           {name:'盐',amount:'1勺'},
           {name:'香油',amount:'几滴'},
           {name:'清水',amount:'3碗(约750ml)'},
         ],
         steps:[
           '紫菜撕成小碎块，鸡蛋充分打散',
           '锅中加清水大火烧开',
           '放入紫菜煮30秒',
           '转圈淋入蛋液，等10秒再用筷子轻轻搅散',
           '加盐、香油调味',
           '撒葱花出锅',
         ],
         tips:'蛋液淋入后不要立即搅动，等10秒蛋花更漂亮成型；紫菜不宜久煮保持鲜味。'
       }},
      {name:'熟食米饭+例汤',emoji:'🍚',role:'主食',roleColor:'var(--purple)',badge:'熟食联动',badgeColor:'#8b5cf6',bg:'linear-gradient(135deg,#ede9fe,#ddd6fe)',
       desc:'即买即食·省时省力',ingr:[{n:'熟食米饭',c:'high'},{n:'例汤',c:''}],
       recipe:{
         servings:'2人份',time:'3分钟',difficulty:'极简',calories:'约250千卡',
         ingredients:[
           {name:'熟食米饭',amount:'2份',note:'超市熟食区'},
           {name:'例汤',amount:'2份',note:'当日例汤'},
         ],
         steps:[
           '米饭微波炉高火加热2分钟',
           '例汤倒入锅中加热至沸腾',
           '搭配主菜即可食用',
         ],
         tips:'超市熟食区即买即食，搭配青椒肉丝和麻婆豆腐，省去煮饭时间。'
       }},
    ],
    package:{
      title:'青椒肉丝 2人份备菜包',
      emoji:'🫑',
      now:25.8, old:32, save:'省 ¥6.2',
      items:[
        {n:'青椒(切丝)',tag:'1天临期',qty:'200g',em:'danger'},
        {n:'猪肉丝',tag:'库存偏高',qty:'300g',em:'warn'},
        {n:'蒜末',tag:'配料',qty:'1份'},
        {n:'酱油料包',tag:'调料',qty:'1包'},
      ],
      link:'+¥6 得 熟食米饭2份+例汤2份（原价¥18）',
      linkText:'熟食区联动'
    },
    reach:{
      push:{title:'今晚15分钟做青椒肉丝 🌧️',body:'雨天就该吃口热乎的！青椒肉丝2人份备菜包已为你配好，切好洗好，回家下锅即炒。套餐价 ¥25.8，搭配米饭例汤更划算～',cta:'立即购买备菜包',time:'17:30 推送 · 家庭客群'},
      screen:{dish:'青椒肉丝套餐',sub:'回家15分钟 · 两人热乎一顿',steps:['青椒切丝200g','猪肉丝300g','热锅快炒3分钟','淋酱出锅'],price:'25.8',unit:'2人份'},
      staff:[
        {t:'拣货：青椒切丝200g ×40份、猪肉丝300g ×40份',when:'09:00 前完成'},
        {t:'布置 <b>场景堆头</b>：生鲜区入口·青椒肉丝主题陈列',when:'10:00 前完成'},
        {t:'熟食区备 <b>米饭+例汤</b> 联动套餐 80 份',when:'16:00 前完成'},
        {t:'会员 App 推送"今晚菜单"（家庭客群）',when:'17:30 准时'},
      ],
      display:{main:'青椒肉丝堆头',side:'豆腐/麻婆豆腐',cooked:'米饭例汤联动',entrance:'场景包入口'}
    },
    value:{
      kpis:[
        {label:'预计减损',val:'¥2,840',sub:'青椒+豆腐 <span class="up">100%售出</span>',color:'good',icon:'♻️'},
        {label:'客单价提升',val:'+18%',sub:'套餐连带 3.8件/单',color:'up',icon:'💰'},
        {label:'熟食区客流',val:'+35%',sub:'米饭例汤联动带动',color:'up',icon:'🔥'},
        {label:'会员打开率',val:'+27%',sub:'每日菜单推送养成习惯',color:'up',icon:'📱'},
      ],
      compare:[
        {label:'临期售价',trad:50,scene:80,tradLabel:'5折',sceneLabel:'8折'},
        {label:'连带件数',trad:1.1,scene:3.8,tradLabel:'1.1',sceneLabel:'3.8'},
        {label:'客单价',trad:38,scene:62,tradLabel:'¥38',sceneLabel:'¥62'},
        {label:'损耗率',trad:8,scene:1.5,tradLabel:'8%',sceneLabel:'1.5%'},
      ]
    }
  },

  s2: {
    name:'高温清凉', icon:'☀️',
    date:'2026-07-12 周日',
    weather:{icon:'☀️',text:'36°C 高温',desc:'酷暑·清淡凉拌需求上升'},
    situation:{
      inventory:[
        {name:'黄瓜',stock:'60kg',level:70,days:'1天临期',status:'danger'},
        {name:'冬瓜',stock:'45kg',level:85,days:'库存偏高',status:'warn'},
        {name:'排骨',stock:'35kg',level:60,days:'2天临期',status:'danger'},
        {name:'木耳(干)',stock:'80包',level:50,days:'正常',status:'ok'},
        {name:'绿豆',stock:'100袋',level:65,days:'解暑热销',status:'ok'},
        {name:'凉皮',stock:'90份',level:75,days:'熟食区',status:'ok'},
      ],
      community:{type:'写字楼白领+居民混合',radius:'3km',peak:'12:00 午间+19:00 晚间',office:'3栋写字楼',kids:'学区房占比20%'},
      flow:'预计 1,120 人',
      hot:'凉皮 · 绿豆汤 · 凉拌黄瓜 · 冬瓜排骨汤'
    },
    reasoning:[
      {tag:'danger',tagText:'临期',text:'检测到 <b>黄瓜</b> 1 天临期 + <b>木耳</b> 库存 <span class="arrow">→</span> 匹配菜谱 <b>凉拌黄瓜木耳</b>'},
      {tag:'danger',tagText:'临期',text:'检测到 <b>排骨</b> 2 天临期 + <b>冬瓜</b> 库存偏高 <span class="arrow">→</span> 匹配菜谱 <b>冬瓜排骨汤</b>'},
      {tag:'info',tagText:'场景',text:'36°C 高温 <b>清淡/凉拌需求↑</b> + 解暑需求 <span class="arrow">→</span> 联动 <b>绿豆汤+凉皮</b>'},
      {tag:'ok',tagText:'客群',text:'写字楼白领午间 + 居民晚间 <span class="arrow">→</span> 双时段推送，推荐 <b>轻食单人份</b>'},
      {tag:'warn',tagText:'组合',text:'组合优化：凉拌黄瓜木耳(主)+冬瓜排骨汤+绿豆汤+凉皮 <span class="arrow">→</span> 清凉主题套餐'},
    ],
    menu:[
      {name:'凉拌黄瓜木耳',emoji:'🥒',role:'主菜',roleColor:'var(--green)',badge:'今日主推',badgeColor:'#22c55e',bg:'linear-gradient(135deg,#dcfce7,#bbf7d0)',
       desc:'清脆爽口·开胃解暑',ingr:[{n:'黄瓜',c:'urgent'},{n:'木耳',c:''},{n:'蒜',c:''},{n:'香油',c:''}],
       recipe:{
         servings:'1-2人份',time:'10分钟',difficulty:'简单',calories:'约120千卡',
         ingredients:[
           {name:'黄瓜',amount:'1根(约200g)',note:'拍碎'},
           {name:'干木耳',amount:'10g',note:'提前泡发'},
           {name:'蒜',amount:'3瓣',note:'切末'},
           {name:'生抽',amount:'2勺'},
           {name:'陈醋',amount:'2勺'},
           {name:'香油',amount:'1勺'},
           {name:'白糖',amount:'半勺'},
           {name:'盐',amount:'适量'},
           {name:'小米辣',amount:'2个',note:'可选'},
         ],
         steps:[
           '干木耳提前用冷水泡发1小时，焯水1分钟过凉沥干',
           '黄瓜用刀面拍碎，切成小段',
           '蒜切末，小米辣切圈',
           '将黄瓜、木耳放入碗中',
           '加入生抽、醋、糖、盐、蒜末搅拌均匀',
           '淋香油，撒小米辣即可',
         ],
         tips:'黄瓜拍碎比切更容易入味；冰镇后食用更爽口；木耳一定要焯水煮熟。'
       }},
      {name:'冬瓜排骨汤',emoji:'🍲',role:'汤品',roleColor:'var(--blue)',badge:'清临期',badgeColor:'#3b82f6',bg:'linear-gradient(135deg,#dbeafe,#bfdbfe)',
       desc:'清淡滋补·清热解暑',ingr:[{n:'冬瓜',c:'high'},{n:'排骨',c:'urgent'},{n:'姜',c:''}],
       recipe:{
         servings:'2-3人份',time:'40分钟',difficulty:'简单',calories:'约350千卡',
         ingredients:[
           {name:'冬瓜',amount:'300g',note:'去皮切大块'},
           {name:'排骨',amount:'400g'},
           {name:'姜',amount:'3片'},
           {name:'葱',amount:'2根'},
           {name:'料酒',amount:'1勺'},
           {name:'盐',amount:'适量'},
           {name:'清水',amount:'适量'},
         ],
         steps:[
           '排骨冷水下锅，加料酒、姜片，大火煮开撇去浮沫',
           '捞出排骨用温水冲洗干净',
           '砂锅加足量清水，放入排骨、姜片，大火烧开转最小火炖30分钟',
           '冬瓜去皮去瓤，切3cm大块',
           '放入冬瓜继续炖10分钟至透明',
           '加盐调味，撒葱花出锅',
         ],
         tips:'排骨先焯水汤更清澈；小火慢炖汤更鲜美；冬瓜不要切太小以免炖烂。'
       }},
      {name:'绿豆汤',emoji:'🥣',role:'饮品',roleColor:'var(--green)',badge:'解暑',badgeColor:'#22c55e',bg:'linear-gradient(135deg,#dcfce7,#bbf7d0)',
       desc:'冰镇解暑·夏日必备',ingr:[{n:'绿豆',c:''}],
       recipe:{
         servings:'2-3人份',time:'30分钟',difficulty:'简单',calories:'约150千卡',
         ingredients:[
           {name:'绿豆',amount:'100g'},
           {name:'清水',amount:'1.5L'},
           {name:'冰糖',amount:'30g',note:'可选'},
         ],
         steps:[
           '绿豆洗净，提前浸泡1小时（更易煮开花）',
           '锅中加清水大火烧开',
           '倒入绿豆，大火煮沸',
           '转最小火煮20分钟至绿豆开花',
           '加冰糖煮至融化',
           '自然冷却后冰镇饮用',
         ],
         tips:'想保持汤色碧绿，煮制时不要频繁开盖；加几滴柠檬汁可防止氧化变色。'
       }},
      {name:'凉皮(熟食)',emoji:'🍜',role:'主食',roleColor:'var(--purple)',badge:'熟食联动',badgeColor:'#8b5cf6',bg:'linear-gradient(135deg,#ede9fe,#ddd6fe)',
       desc:'即买即食·酸辣开胃',ingr:[{n:'凉皮',c:''},{n:'黄瓜丝',c:'urgent'}],
       recipe:{
         servings:'1人份',time:'3分钟',difficulty:'极简',calories:'约300千卡',
         ingredients:[
           {name:'凉皮',amount:'1份',note:'超市熟食区'},
           {name:'黄瓜丝',amount:'适量'},
           {name:'面筋',amount:'适量'},
           {name:'辣椒油',amount:'1勺'},
           {name:'蒜水',amount:'1勺'},
           {name:'陈醋',amount:'2勺'},
           {name:'生抽',amount:'1勺'},
         ],
         steps:[
           '凉皮抖散放入盘中',
           '铺上黄瓜丝、面筋',
           '淋蒜水、醋、生抽',
           '浇辣椒油，拌匀即可食用',
         ],
         tips:'超市熟食区即买即食；冰镇后食用更爽口；辣椒油量根据口味调整。'
       }},
    ],
    package:{
      title:'清凉一夏 轻食单人套餐',
      emoji:'🥒',
      now:19.9, old:28, save:'省 ¥8.1',
      items:[
        {n:'凉拌黄瓜木耳',tag:'1天临期',qty:'1份',em:'danger'},
        {n:'凉皮',tag:'熟食',qty:'1份'},
        {n:'绿豆汤(冰镇)',tag:'解暑',qty:'1杯'},
        {n:'冬瓜排骨汤',tag:'2天临期',qty:'小份',em:'danger'},
      ],
      link:'+¥3 加购 冰镇绿豆汤大杯（限午间时段）',
      linkText:'午间时段加购'
    },
    reach:{
      push:{title:'36°C 该吃点凉的了 🥒',body:'凉拌黄瓜木耳+凉皮+绿豆汤，清凉轻食单人套餐 ¥19.9，写字楼午间即买即食，回家不用开火！',cta:'查看清凉套餐',time:'11:30 / 18:30 双时段推送'},
      screen:{dish:'清凉轻食套餐',sub:'36°C 不开火 · 即买即食',steps:['凉拌黄瓜木耳','冰镇绿豆汤','酸辣凉皮','冬瓜排骨汤'],price:'19.9',unit:'单人份'},
      staff:[
        {t:'拣货：黄瓜切配 ×60份、木耳泡发 ×60份',when:'09:30 前完成'},
        {t:'熟食区备 <b>凉皮+绿豆汤</b> 联动套餐 100 份',when:'11:00 前完成'},
        {t:'布置 <b>清凉主题堆头</b>：入口冰柜旁·蓝色清凉视觉',when:'10:30 前完成'},
        {t:'双时段推送：11:30 写字楼 / 18:30 居民',when:'准时触发'},
      ],
      display:{main:'清凉轻食堆头',side:'绿豆汤冰柜',cooked:'凉皮熟食区',entrance:'冰镇饮品入口'}
    },
    value:{
      kpis:[
        {label:'预计减损',val:'¥3,120',sub:'黄瓜+排骨 <span class="up">清空</span>',color:'good',icon:'♻️'},
        {label:'客单价提升',val:'+22%',sub:'轻食套餐连带 4.2件/单',color:'up',icon:'💰'},
        {label:'熟食午间销量',val:'+45%',sub:'凉皮绿豆汤带动',color:'up',icon:'🔥'},
        {label:'白领到店率',val:'+31%',sub:'午间精准触达',color:'up',icon:'📊'},
      ],
      compare:[
        {label:'临期售价',trad:50,scene:71,tradLabel:'5折',sceneLabel:'7.1折'},
        {label:'连带件数',trad:1.2,scene:4.2,tradLabel:'1.2',sceneLabel:'4.2'},
        {label:'客单价',trad:32,scene:55,tradLabel:'¥32',sceneLabel:'¥55'},
        {label:'损耗率',trad:9,scene:2,tradLabel:'9%',sceneLabel:'2%'},
      ]
    }
  },

  s3: {
    name:'三伏家庭', icon:'👨‍👩‍👧',
    date:'2026-07-15 周三',
    weather:{icon:'⛅',text:'晴 25°C',desc:'宜聚餐·家庭烹饪需求强'},
    situation:{
      inventory:[
        {name:'五花肉',stock:'40kg',level:88,days:'库存偏高',status:'warn'},
        {name:'番茄',stock:'55kg',level:60,days:'2天临期',status:'danger'},
        {name:'鸡蛋',stock:'180盒',level:45,days:'正常',status:'ok'},
        {name:'紫菜',stock:'50包',level:30,days:'正常',status:'ok'},
        {name:'大米',stock:'300袋',level:70,days:'家庭装热销',status:'ok'},
        {name:'可乐',stock:'200瓶',level:80,days:'库存偏高',status:'warn'},
      ],
      community:{type:'家庭聚餐为主',radius:'3km',peak:'全天客流',office:'周边社区',kids:'学区房占比40%'},
      flow:'预计 1,380 人',
      hot:'红烧肉 · 番茄炒蛋 · 糖醋排骨 · 火锅'
    },
    reasoning:[
      {tag:'warn',tagText:'高库存',text:'检测到 <b>五花肉</b> 库存偏高 <span class="arrow">→</span> 匹配菜谱 <b>红烧肉</b>（家庭聚餐硬菜）'},
      {tag:'danger',tagText:'临期',text:'检测到 <b>番茄</b> 2 天临期 + 鸡蛋充足 <span class="arrow">→</span> 匹配菜谱 <b>番茄炒蛋</b>'},
      {tag:'info',tagText:'三伏',text:'三伏时节 <b>家庭清淡消暑需求↑</b> + 可乐库存高 <span class="arrow">→</span> 联动 <b>可乐+大米</b> 家庭装'},
      {tag:'ok',tagText:'客群',text:'家庭客群·全天客流 <span class="arrow">→</span> 推荐 <b>3-4人家庭套餐</b>，上午推送备菜'},
      {tag:'warn',tagText:'组合',text:'组合优化：红烧肉(硬菜)+番茄炒蛋+紫菜蛋花汤+大米 <span class="arrow">→</span> 家庭聚餐全套餐'},
    ],
    menu:[
      {name:'红烧肉',emoji:'🥩',role:'硬菜',roleColor:'var(--warm)',badge:'今日主推',badgeColor:'#f97316',bg:'linear-gradient(135deg,#fed7aa,#fdba74)',
       desc:'软糯入味·家庭聚餐C位',ingr:[{n:'五花肉',c:'high'},{n:'冰糖',c:''},{n:'酱油',c:''},{n:'八角',c:''}],
       recipe:{
         servings:'3-4人份',time:'60分钟',difficulty:'中等',calories:'约580千卡',
         ingredients:[
           {name:'五花肉',amount:'500g',note:'切3cm方块'},
           {name:'冰糖',amount:'30g'},
           {name:'生抽',amount:'3勺'},
           {name:'老抽',amount:'1勺'},
           {name:'料酒',amount:'2勺'},
           {name:'八角',amount:'2个'},
           {name:'桂皮',amount:'1小块'},
           {name:'香叶',amount:'2片'},
           {name:'姜',amount:'4片'},
           {name:'葱',amount:'2根'},
           {name:'热水',amount:'适量'},
         ],
         steps:[
           '五花肉切3cm见方的块',
           '冷水下锅，加料酒、姜片焯水5分钟，捞出温水冲洗沥干',
           '锅中放少许油，小火炒冰糖至枣红色起密集小泡',
           '迅速下肉块翻炒，均匀裹上糖色',
           '加生抽、老抽、料酒翻炒上色',
           '加热水没过肉块，放八角、桂皮、香叶、葱段',
           '大火烧开后转最小火，盖盖炖40分钟',
           '开盖大火收汁至浓稠发亮',
           '出锅装盘',
         ],
         tips:'炒糖色务必小火慢炒，焦了会发苦；一定要加热水不能加冷水，否则肉会收缩变硬。'
       }},
      {name:'番茄炒蛋',emoji:'🍅',role:'配菜',roleColor:'var(--red)',badge:'清临期',badgeColor:'#ef4444',bg:'linear-gradient(135deg,#fecaca,#fca5a5)',
       desc:'国民家常·老少皆宜',ingr:[{n:'番茄',c:'urgent'},{n:'鸡蛋',c:''}],
       recipe:{
         servings:'3人份',time:'8分钟',difficulty:'简单',calories:'约220千卡',
         ingredients:[
           {name:'番茄',amount:'3个',note:'去皮切块'},
           {name:'鸡蛋',amount:'4个'},
           {name:'葱',amount:'1根'},
           {name:'白糖',amount:'1勺'},
           {name:'盐',amount:'1勺'},
           {name:'生抽',amount:'半勺'},
           {name:'食用油',amount:'3勺'},
         ],
         steps:[
           '番茄顶部划十字，开水烫30秒去皮，切滚刀块',
           '鸡蛋打散，加少许盐搅匀',
           '热锅多油，倒入蛋液炒至凝固成块，盛出备用',
           '锅中余油下番茄块，中火翻炒出汁',
           '加糖、盐、生抽调味',
           '鸡蛋回锅翻炒均匀',
           '撒葱花出锅',
         ],
         tips:'番茄去皮口感更好；鸡蛋先炒到半熟保持嫩滑；多放点油炒蛋更香。'
       }},
      {name:'紫菜蛋花汤',emoji:'🍵',role:'汤品',roleColor:'var(--blue)',badge:'配汤',badgeColor:'#3b82f6',bg:'linear-gradient(135deg,#dbeafe,#bfdbfe)',
       desc:'清淡解腻·3分钟出锅',ingr:[{n:'紫菜',c:''},{n:'鸡蛋',c:''}],
       recipe:{
         servings:'4人份',time:'5分钟',difficulty:'简单',calories:'约90千卡',
         ingredients:[
           {name:'干紫菜',amount:'1小把(约8g)'},
           {name:'鸡蛋',amount:'3个'},
           {name:'葱花',amount:'适量'},
           {name:'盐',amount:'1.5勺'},
           {name:'香油',amount:'几滴'},
           {name:'清水',amount:'4碗(约1000ml)'},
         ],
         steps:[
           '紫菜撕碎，鸡蛋打散',
           '锅中加水大火烧开',
           '放入紫菜煮30秒',
           '转圈淋入蛋液，等10秒再轻轻搅散',
           '加盐、香油调味',
           '撒葱花出锅',
         ],
         tips:'搭配红烧肉解腻最佳；蛋液不要立即搅动，蛋花更漂亮。'
       }},
      {name:'家庭装大米+可乐',emoji:'🍚',role:'主食',roleColor:'var(--purple)',badge:'连带',badgeColor:'#8b5cf6',bg:'linear-gradient(135deg,#ede9fe,#ddd6fe)',
       desc:'周末囤货·聚餐必备',ingr:[{n:'大米',c:''},{n:'可乐',c:'high'}],
       recipe:{
         servings:'4人份',time:'30分钟',difficulty:'简单',calories:'约400千卡',
         ingredients:[
           {name:'大米',amount:'2杯(约400g)'},
           {name:'清水',amount:'适量',note:'米:水=1:1.2'},
           {name:'可乐',amount:'1瓶(2L)',note:'冰镇'},
         ],
         steps:[
           '大米淘洗2遍，不要过度搓洗',
           '按米水比1:1.2加水',
           '电饭煲选择煮饭模式',
           '煮好后焖5分钟再开盖',
           '用饭勺翻松，盛饭',
           '可乐冰镇后搭配饮用',
         ],
         tips:'周末聚餐标配；大米不要淘洗太多次以免营养流失；焖5分钟米饭更饱满。'
       }},
    ],
    package:{
      title:'三伏家庭聚餐 3-4人套餐',
      emoji:'👨‍👩‍👧',
      now:68.8, old:89, save:'省 ¥20.2',
      items:[
        {n:'五花肉(切块)',tag:'库存偏高',qty:'500g',em:'warn'},
        {n:'番茄',tag:'2天临期',qty:'4个',em:'danger'},
        {n:'鸡蛋',tag:'充足',qty:'6个'},
        {n:'紫菜+大米+可乐',tag:'连带',qty:'家庭装'},
      ],
      link:'+¥9.9 得 可乐2L+八角料包（周末囤货价）',
      linkText:'周末囤货加购'
    },
    reach:{
      push:{title:'周末给家人做顿好的 🥩',body:'红烧肉+番茄炒蛋+紫菜蛋花汤，3-4人家庭聚餐套餐 ¥68.8，食材已配齐，周末在家露一手！加购可乐更划算～',cta:'查看家庭套餐',time:'10:00 推送 · 家庭客群'},
      screen:{dish:'三伏家庭聚餐套餐',sub:'3-4人份 · 在家露一手',steps:['五花肉切块焯水','炒糖色炖40分钟','番茄炒蛋3分钟','紫菜蛋花汤'],price:'68.8',unit:'3-4人份'},
      staff:[
        {t:'拣货：五花肉切块 ×50份、番茄 ×50份',when:'08:30 前完成'},
        {t:'布置 <b>家庭聚餐主题区</b>：生鲜区中央岛台',when:'09:30 前完成'},
        {t:'大米+可乐 <b>连带堆头</b>：套餐旁陈列',when:'09:30 前完成'},
        {t:'下午推送"三伏家庭菜单"（家庭客群）',when:'16:30 准时'},
      ],
      display:{main:'家庭聚餐岛台',side:'番茄鸡蛋区',cooked:'大米可乐堆头',entrance:'套餐入口'}
    },
    value:{
      kpis:[
        {label:'预计减损',val:'¥1,960',sub:'番茄 <span class="up">清空</span>',color:'good',icon:'♻️'},
        {label:'客单价提升',val:'+28%',sub:'家庭套餐连带 5.2件/单',color:'up',icon:'💰'},
        {label:'大米可乐销量',val:'+52%',sub:'连带堆头带动',color:'up',icon:'🔥'},
        {label:'周末到店率',val:'+19%',sub:'家庭客群精准触达',color:'up',icon:'📊'},
      ],
      compare:[
        {label:'临期售价',trad:50,scene:82,tradLabel:'5折',sceneLabel:'8.2折'},
        {label:'连带件数',trad:1.3,scene:5.2,tradLabel:'1.3',sceneLabel:'5.2'},
        {label:'客单价',trad:45,scene:89,tradLabel:'¥45',sceneLabel:'¥89'},
        {label:'损耗率',trad:7,scene:1.2,tradLabel:'7%',sceneLabel:'1.2%'},
      ]
    }
  },

  s4: {
    name:'冬至节日', icon:'🥟',
    date:'2026-12-22 周二',
    weather:{icon:'❄️',text:'冬至 2°C',desc:'节气·饺子需求爆发'},
    situation:{
      inventory:[
        {name:'猪肉馅',stock:'60kg',level:82,days:'2天临期',status:'danger'},
        {name:'白菜',stock:'70kg',level:75,days:'1天临期',status:'danger'},
        {name:'面粉',stock:'200袋',level:90,days:'库存偏高',status:'warn'},
        {name:'韭菜',stock:'30kg',level:50,days:'正常',status:'ok'},
        {name:'醋/蒜',stock:'150份',level:40,days:'正常',status:'ok'},
        {name:'速冻水饺',stock:'400袋',level:85,days:'节日备货',status:'ok'},
      ],
      community:{type:'北方社区·家庭为主',radius:'3km',peak:'17:00-19:00 下班',office:'周边社区',kids:'学区房占比45%'},
      flow:'预计 1,560 人',
      hot:'手工水饺 · 速冻水饺 · 羊肉汤 · 饺子皮'
    },
    reasoning:[
      {tag:'danger',tagText:'临期',text:'检测到 <b>猪肉馅</b> 2 天临期 + <b>白菜</b> 1 天临期 + <b>面粉</b> 库存偏高 <span class="arrow">→</span> 匹配菜谱 <b>白菜猪肉水饺</b>'},
      {tag:'info',tagText:'节气',text:'<b>冬至</b> 饺子需求爆发 + 北方社区传统 <span class="arrow">→</span> 主推 <b>手工水饺套餐</b>'},
      {tag:'ok',tagText:'客群',text:'家庭客群·下班包饺子传统 <span class="arrow">→</span> 推荐 <b>全家动手包饺子套餐</b>，17:00 推送'},
      {tag:'warn',tagText:'联动',text:'速冻水饺库存充足 <span class="arrow">→</span> 双线：手工DIY + 速冻即买即煮'},
      {tag:'warn',tagText:'组合',text:'组合优化：手工水饺(主)+韭菜鸡蛋饺+醋蒜蘸料+速冻备选 <span class="arrow">→</span> 冬至饺子全场景'},
    ],
    menu:[
      {name:'白菜猪肉手工饺',emoji:'🥟',role:'主推',roleColor:'var(--warm)',badge:'今日主推',badgeColor:'#f97316',bg:'linear-gradient(135deg,#fef3c7,#fde68a)',
       desc:'冬至传统·全家动手',ingr:[{n:'猪肉馅',c:'urgent'},{n:'白菜',c:'urgent'},{n:'面粉',c:'high'}],
       recipe:{
         servings:'4-5人份',time:'90分钟',difficulty:'中等',calories:'约420千卡',
         ingredients:[
           {name:'猪肉馅',amount:'500g',note:'三肥七瘦'},
           {name:'白菜',amount:'300g'},
           {name:'面粉',amount:'400g'},
           {name:'温水',amount:'200ml'},
           {name:'葱',amount:'2根',note:'切末'},
           {name:'姜',amount:'1块',note:'切末'},
           {name:'生抽',amount:'2勺'},
           {name:'料酒',amount:'1勺'},
           {name:'盐',amount:'1勺'},
           {name:'香油',amount:'1勺'},
           {name:'胡椒粉',amount:'半勺'},
         ],
         steps:[
           '面粉加温水慢慢搅拌，揉成光滑面团，盖湿布醒30分钟',
           '白菜切碎，撒少许盐杀水10分钟，挤干水分',
           '肉馅加葱姜末、生抽、料酒、盐、胡椒粉、香油，顺一个方向搅上劲',
           '拌入挤干水分的白菜，搅拌均匀',
           '面团搓成长条，切成小剂子，擀成中间厚边缘薄的圆皮',
           '取适量馅料放在皮中央，对折捏紧封口',
           '锅中大火烧开水量要足，下饺子',
           '水开后点半碗凉水，重复3次',
           '饺子全部浮起、膨胀鼓肚即熟，捞出装盘',
         ],
         tips:'白菜一定要挤干水分，馅才不塌不破皮；和面用温水，饺子皮更软更有韧性；煮饺子的水要宽（多），点水3次是关键。'
       }},
      {name:'韭菜鸡蛋饺',emoji:'🥟',role:'搭配',roleColor:'var(--green)',badge:'素馅',badgeColor:'#22c55e',bg:'linear-gradient(135deg,#dcfce7,#bbf7d0)',
       desc:'鲜香清爽·一荤一素',ingr:[{n:'韭菜',c:''},{n:'鸡蛋',c:''},{n:'面粉',c:'high'}],
       recipe:{
         servings:'4人份',time:'80分钟',difficulty:'中等',calories:'约350千卡',
         ingredients:[
           {name:'韭菜',amount:'300g'},
           {name:'鸡蛋',amount:'4个'},
           {name:'面粉',amount:'400g'},
           {name:'温水',amount:'200ml'},
           {name:'虾皮',amount:'1勺'},
           {name:'盐',amount:'1勺'},
           {name:'香油',amount:'1勺'},
           {name:'食用油',amount:'2勺'},
         ],
         steps:[
           '面粉加温水和面，揉光滑醒30分钟',
           '韭菜洗净晾干，切碎',
           '鸡蛋打散炒碎，放凉备用',
           '韭菜、鸡蛋、虾皮混合，加盐、香油拌匀',
           '最后淋食用油拌匀（锁住水分防出水）',
           '面团搓条切剂，擀成圆皮',
           '包入馅料捏紧',
           '烧开水下饺，点水3次至浮起即熟',
         ],
         tips:'韭菜洗净后一定要晾干再切；馅料在包之前再放盐，防止出水；加食用油可以锁水。'
       }},
      {name:'醋蒜蘸料',emoji:'🧄',role:'调料',roleColor:'var(--purple)',badge:'标配',badgeColor:'#8b5cf6',bg:'linear-gradient(135deg,#ede9fe,#ddd6fe)',
       desc:'饺子灵魂·即配即用',ingr:[{n:'醋',c:''},{n:'蒜',c:''}],
       recipe:{
         servings:'4人份',time:'2分钟',difficulty:'极简',calories:'约20千卡',
         ingredients:[
           {name:'陈醋',amount:'3勺'},
           {name:'蒜',amount:'5瓣',note:'捣成蒜泥'},
           {name:'生抽',amount:'1勺'},
           {name:'辣椒油',amount:'1勺',note:'可选'},
         ],
         steps:[
           '蒜瓣加少许盐，捣成细腻蒜泥',
           '加陈醋、生抽搅拌均匀',
           '淋辣椒油即可',
         ],
         tips:'吃饺子的灵魂搭档；蒜泥越细越香；蒜泥加少许盐捣更容易出蒜汁。'
       }},
      {name:'速冻水饺(备选)',emoji:'❄️',role:'即食',roleColor:'var(--blue)',badge:'即买即煮',badgeColor:'#3b82f6',bg:'linear-gradient(135deg,#dbeafe,#bfdbfe)',
       desc:'没空包？即买即煮',ingr:[{n:'速冻水饺',c:''}],
       recipe:{
         servings:'2人份',time:'15分钟',difficulty:'简单',calories:'约380千卡',
         ingredients:[
           {name:'速冻水饺',amount:'1袋(约30个)'},
           {name:'清水',amount:'适量'},
           {name:'盐',amount:'少许',note:'防粘'},
         ],
         steps:[
           '锅中加足量清水大火烧开',
           '水中加少许盐防粘',
           '下速冻饺子，用勺背轻轻推动防粘底',
           '水开后点半碗凉水',
           '重复点水3-4次',
           '饺子全部浮起、鼓肚即熟，捞出',
         ],
         tips:'没空包饺子也能过冬至；水中加盐可防止饺子粘连破皮；速冻饺子不需要解冻直接下锅。'
       }},
    ],
    package:{
      title:'冬至全家动手包饺子套餐',
      emoji:'🥟',
      now:39.9, old:52, save:'省 ¥12.1',
      items:[
        {n:'猪肉馅',tag:'2天临期',qty:'500g',em:'danger'},
        {n:'白菜',tag:'1天临期',qty:'1颗',em:'danger'},
        {n:'面粉+韭菜+鸡蛋',tag:'DIY包',qty:'1套'},
        {n:'醋蒜蘸料',tag:'标配',qty:'2份'},
      ],
      link:'+¥12.9 得 速冻水饺2袋（没空包也能过冬至）',
      linkText:'速冻备选加购'
    },
    reach:{
      push:{title:'冬至快乐！今晚包饺子吧 🥟',body:'白菜猪肉+韭菜鸡蛋，全家动手包饺子套餐 ¥39.9，馅料皮子全配好。冬至的仪式感，从一顿热腾腾的饺子开始～',cta:'查看饺子套餐',time:'17:00 推送 · 全客群'},
      screen:{dish:'冬至包饺子套餐',sub:'全家动手 · 冬至仪式感',steps:['和面擀皮','调白菜猪肉馅','包饺子30分钟','下锅煮3开'],price:'39.9',unit:'4-5人份'},
      staff:[
        {t:'拣货：猪肉馅分装 ×60份、白菜 ×60颗',when:'08:00 前完成'},
        {t:'布置 <b>冬至饺子主题区</b>：生鲜区入口·节日视觉',when:'09:00 前完成'},
        {t:'面粉+韭菜+鸡蛋 <b>DIY套装</b> 预包装 60 套',when:'10:00 前完成'},
        {t:'速冻水饺 <b>备选堆头</b> + 节日推送',when:'16:00 / 17:00'},
      ],
      display:{main:'冬至饺子主题区',side:'韭菜鸡蛋区',cooked:'速冻水饺堆头',entrance:'节日套餐入口'}
    },
    value:{
      kpis:[
        {label:'预计减损',val:'¥4,200',sub:'猪肉馅+白菜 <span class="up">清空</span>',color:'good',icon:'♻️'},
        {label:'客单价提升',val:'+24%',sub:'饺子套餐连带 4.8件/单',color:'up',icon:'💰'},
        {label:'面粉销量',val:'+68%',sub:'DIY套装带动',color:'up',icon:'🔥'},
        {label:'节日到店率',val:'+42%',sub:'冬至主题精准触达',color:'up',icon:'📊'},
      ],
      compare:[
        {label:'临期售价',trad:50,scene:77,tradLabel:'5折',sceneLabel:'7.7折'},
        {label:'连带件数',trad:1.4,scene:4.8,tradLabel:'1.4',sceneLabel:'4.8'},
        {label:'客单价',trad:40,scene:72,tradLabel:'¥40',sceneLabel:'¥72'},
        {label:'损耗率',trad:8,scene:1,tradLabel:'8%',sceneLabel:'1%'},
      ]
    }
  }
};
