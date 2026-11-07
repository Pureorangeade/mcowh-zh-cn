# 待终审批阅清单

更新：2026-11-08，第0065批用户批注已应用。

**F01—F17已确认；F18—F21仍待处理，保留原编号。** 其余18项是按全局规则暂留英文的人名问题，可继续跳过。当前22项终审涉及483条关联记录；只有下列4项机制问题需要以后另作判断，共7条说明。

已完成的21项处理见[0065批阅结果](USER_REVIEW_0065.md)。旧F01—F21全文快照保存在work/final-review-0065/before/docs/FINAL_REVIEW.md；原编号映射仍保存在final-review-reading-manifest.json，不会把F18改称F01。

可回复“F18 按英文／按日文／指定译文／继续暂缓”。“按英文／按日文”表示采用相应版本的中文含义；“保留英文原句”表示保留英文形式。当前均维持现英文版含义，等待后续判断。

## 仍待处理

| 编号 | 疑点 | 关联条数 |
| --- | --- | ---: |
| F18 | 古代拳套：英文为命中+50%、暴击+100%；日文为暴击+50%、连击+100%。 | 1 |
| F19 | 绝望之戒：英文为魔力+25%；日文为魔法伤害+25%。 | 1 |
| F20 | 光之灾厄速度：英文3 times faster，现稿按3倍；日文3割増し，即增加30%。 | 1 |
| F21 | 四处世界规则：英文3倍经验，日文增加30%的经验（1.3倍）。 | 4 |

## F18：古代拳套：英文为命中+50%、暴击+100%；日文为暴击+50%、连击+100%。

问题ID：`ancient-hand-stat-difference`。

当前决定：用户再次确认继续待处理；维持当前英文版含义，不自行改用日文。

条目：`db/3/155/1`。

英文原文：
```text
An extremely light blunt weapon made with ancient
skills. It was restored with the utmost skill, but be
careful with the \c[61]Durability\c[0]. \c[61]ACC\c[0] \c[60]+50%\c[0], \c[61]Crit\c[0] \c[60]+100%\c[0].
```

日文原文：
```text
失われし太古の技術で造られた、非常に軽い打撃武器。
最高の技術で修復したが、\c[61]耐久度\c[0]に不安が残る。
\c[61]必殺率\c[0]\c[60]+50％\c[0]、\c[61]連続攻撃率\c[0]\c[60]+100％\c[0]。
```

当前译文：
```text
以古代技艺打造的轻盈打击武器。
虽以顶尖技艺修复，仍需留意\c[61]耐久度\c[0]。
\c[61]命中率\c[0]\c[60]+50%\c[0]，\c[61]暴击率\c[0]\c[60]+100%\c[0]。
```


## F19：绝望之戒：英文为魔力+25%；日文为魔法伤害+25%。

问题ID：`ring-despair-force-difference`。

当前决定：用户再次确认继续待处理；维持当前英文版含义，不自行改用日文。

条目：`db/5/74/1`。

英文原文：
```text
The ring of a Wiseman who understood the world,
hated people and died alone. \c[61]ST\c[0] decreases
each turn, \c[61]Concentrate\c[0] \c[60]+1\c[0], and \c[61]Force\c[0] \c[60]+25%\c[0].
```

日文原文：
```text
英知に富み世を見通せたがゆえに、人を嫌って
山にこもり、孤独に死んでいった賢者の指輪。
\c[61]ST\c[0]が減り続け、\c[61]集中\c[0]\c[60]+1\c[0]、\c[61]理力ダメージ\c[0]\c[60]+25％\c[0]。
```

当前译文：
```text
看透世事、厌弃人群，最终孤独死去的贤者的戒指。
每回合\c[61]ST\c[0]持续减少，\c[61]集中\c[0]\c[60]+1\c[0]，
\c[61]魔力\c[0]\c[60]+25%\c[0]。
```


## F20：光之灾厄速度：英文3 times faster，现稿按3倍；日文3割増し，即增加30%。

问题ID：`review-shine-raid-speed`。

当前决定：用户再次确认继续待处理；维持当前英文版含义，不自行改用日文。

条目：`db/33/65/1`。

英文原文：
```text
The Shine Raid progresses rapidly
in <WORLD>.
The insatiable light of despair is 3 times faster
but items are slightly better to compensate.
```

日文原文：
```text
シャインレイド急進
絶望の<WORLD>
　絶望の光は無慈悲に世界を飲み込む。3割増しの速度で滅ぶ世界で、
　出現するアイテムの少しの優秀さが、あなたの助けとなるだろう。
```

当前译文：
```text
光之灾厄正在<WORLD>中迅速推进。
贪得无厌的绝望之光速度提高至3倍，
但物品会稍好一些作为补偿。
```


## F21：四处世界规则：英文3倍经验，日文增加30%的经验（1.3倍）。

问题ID：`review-world-experience-multiplier`。

当前决定：用户再次确认继续待处理；维持当前英文版含义，不自行改用日文。

条目：`db/33/90/1`。

英文原文：
```text
Gain levels quickly
in <WORLD>.
You gain 3x experience
but enemies are likewise stronger.
```

日文原文：
```text
経験から大きく成長できる
レベルが上がりやすい<WORLD>
　この世界では、あなたは3割増しで経験を得て成長することができる。
　強敵の待ち受ける世界でも、その力で戦っていけるだろう。
```

当前译文：
```text
在<WORLD>中快速升级。
获得3倍经验，
但敌人也会相应变强。
```

条目：`db/33/98/1`。

英文原文：
```text
Gain levels quickly
in <WORLD>.
You gain 3x experience
but enemies are likewise stronger.
```

日文原文：
```text
経験から大きく成長できる
レベルが上がりやすい<WORLD>
　この世界では、あなたは3割増しで経験を得て成長することができる。
　強敵の待ち受ける世界でも、その力で戦っていけるだろう。
```

当前译文：
```text
在<WORLD>中快速升级。
获得3倍经验，
但敌人也会相应变强。
```

条目：`db/33/99/1`。

英文原文：
```text
An unseen menace awaits
in <WORLD>.
Dangerous traps are set all over the world.
3x EXP should help you survive.
```

日文原文：
```text
不可視の敵意が待ち受ける
罠だらけの<WORLD>
　危険な罠が世界中に多数設置されている。3割増しで得られる経験と、
　出現するアイテムの少しの優秀さが、あなたの助けとなるだろう。
```

当前译文：
```text
在<WORLD>中，看不见的威胁正在等待。
危险陷阱遍布全世界。
3倍EXP应当能帮助你生存。
```

条目：`db/33/100/1`。

英文原文：
```text
Offense is the best defense
in <WORLD>.
Armor is rare. 3x EXP and strong items should help you survive.
```

日文原文：
```text
攻撃は最大の防御
防具が希少な<WORLD>
　あなたを守る防具を拾うことは難しい。3割増しで得られる経験と、
　出現する武器の少しの優秀さが、あなたの助けとなるだろう。

```

当前译文：
```text
在<WORLD>中，进攻就是最好的防御。
护甲很稀有。3倍EXP与强力物品应当能帮助你生存。
```

## 人名暂留英文

以下18项既有人名问题仍保留记录，无需重新逐条答复；其余人名同样遵循全局英文规则，见PERSONAL_NAMES_0064.md。

| 问题ID | 英文姓名 |
| --- | --- |
| name-zeukrees | Zeukrees |
| name-pluton | Pluton |
| name-auris | Auris |
| name-baldur | Baldur |
| name-draco | Draco |
| name-koppa | Koppa |
| name-albert | Albert |
| name-nami | Nami |
| name-cole | Cole |
| name-merril | Merril |
| name-aerdou | Aerdou |
| name-coco | Coco |
| name-olga | Olga |
| name-creatoire | Creatoire |
| name-lilith | Lilith |
| name-lillith | Lillith |
| name-aria | Aria |
| name-monomi | Monomi |

## 编辑器查看

打开editor/汉化译文编辑器.html，筛选“暂缓，最后终审”。展开“语境不确定？暂缓至最后终审”查看原因。F01—F17不再因这批集中问题进入终审筛选。你自行添加的整条暂缓另行保留。修改并导出JSON后发回聊天合入，浏览器修改不会自动写入游戏。
