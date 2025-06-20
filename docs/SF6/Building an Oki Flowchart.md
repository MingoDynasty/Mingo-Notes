---
tags: ["sf6"]
---

# Building an Oki Flowchart

For the purposes of this article, I will be using Ken as the example.

## Beginner Flowchart - Version 1

A beginner flowchart usually starts like this:

```text
Knockdown -> cr.LP xx cr.LP xx st.LP -> hit -> HP DP -> repeat
                              v---> blocked -> your turn ends
```

In SF6, everyone has chainable lights that can cancel into a special move. This serves as both a hitconfirm and a frame trap. With some exceptions, most characters can use 3 lights (e.g. sorry Guile), and most characters can combo into a special move without spending meter (e.g. sorry Zangief, Dhalsim, etc.).

Now there are a couple issues with this:

1. Due to combo scaling, the reward for landing this combo is very low.
   1. In Ken's case, his combo only does 1590, which is barely more than a throw (1200).
2. Due to the combination of pushback and frame disadvantage, your turn generally ends if it gets blocked.

## Beginner Flowchart - Version 2

A number of characters are blessed with being able to link off of mediums or heavies. For example, Cammy can link off her `cr.HP`, and Chun Li can link off her `st.MP`. In Ken's case, he can link off his `st.MP`. So a slightly improved flowchart might look like this:

```text
Knockdown -> st.MP -> hit -> cr.LP , st.LK xx HP DP -> repeat
             v--> blocked -> your turn ends
```

Doing this ups Ken's damage to 2120, a nice improvement! However, we still have the remaining issue that your turn still ends because `st.MP` is -2 on block.

Some characters are blessed with plus on block buttons (Ken, unfortunately is not one of them). In the above examples, Cammy's `cr.HP` is +1 on block, and Chun Li's `st.MP` is also +1 on block. This makes it so it is still their turn.

Keeping your turn means you can do another mixup. When crafted perfectly, you can have upwards of 3 or more layers of mixups! This means up to 3 chances for your opponent to guess wrong and get put back into the vortex.

**Note**: for practical purposes, these two flowcharts are all you need to get to Master. But if you want to take your game further, then read on.

Now how do we get frame advantage when none of our buttons are plus on block? Introducing...

## Meaties

https://glossary.infil.net/?t=Meaty
Meaties are attacks that hits the opponent on the later frames of the move's active frames. Since attacks always have the same hitstun/blockstun, you will recover sooner and generate more frame advantage.

Meaties also have the added benefit of limiting your opponents' options to block/invincible move/Parry, as anything else they try will simply get hit or counterhit.

## Finding a Good Meaty

One of Ken's weaknesses is that he does not have any plus on block moves (excluding Dragon Lash, because that is just Perfect Parry fodder for high MR opponents, and generally not a good meaty).

To compensate for this, we want to find a button with the following attributes:

1. Minimal pushback so that on block, we can continue with more buttons and/or threaten a throw.
2. As much frame advantage as possible on hit, to allow for stronger combo followups.
3. As much frame advantage as possible on block, so we can continue pressure.
   1. Addendum: also we don't want to get punished on block. Let's keep our oki safe.
4. Recovers fast enough in time to DI back (or cancellable into DI).
   1. Not a requirement, but helps make our oki much safer. In most cases, most meaties are safe to DI anyways. But this does imply that things like Blanka `f+MK` and Aki's `f+HK` are not reliable meaties, because they have very slow recovery and therefore easily lose to DI.

### Calculating Meaty Frame Advantage

To calculate how much frame advantage we get from a perfectly timed meaty, we need to know:

1. Frame advantage on hit
2. Number of active frames
   For example, Ken's `st.LP` is +4 on hit, and has 3 active frames.
   TODO: picture or video zoom up

The formula for calculating meaty frame advantage is:
`frame advantage` + `active frames` - 1 = `frame advantage on perfect meaty`
In Ken's `st.LP` example, he will be +6 on a perfect meaty.
`4 + 3 - 1 = 6`
TODO: video with st.MP xx st.HP xx Run Tatsu , 2x dash , st.LP showing +6

The following is a table of Ken's normals as candidates for meaties:

|            |                          |                          |                   |                                        |                                        |                    |
| ---------- | ------------------------ | ------------------------ | ----------------- | -------------------------------------- | -------------------------------------- | ------------------ |
| **Normal** | **Frame Advantage (oH)** | **Frame Advantage (oB)** | **Active Frames** | **Frame Advantage oH (perfect meaty)** | **Frame Advantage oB (perfect meaty)** | **Safe On Block?** |
| st.LP      | 4                        | -1                       | 3                 | 6                                      | 1                                      | Yes                |
| st.MP      | 4                        | -2                       | 4                 | 7                                      | 1                                      | Yes                |
| st.HP      | 3                        | -2                       | 5                 | 7                                      | 2                                      | Yes                |
| st.LK      | 0                        | -2                       | 2                 | 1                                      | -1                                     | Yes                |
| st.MK      | 3                        | -5                       | 3                 | 5                                      | -3                                     | Yes                |
| st.HK      | 1                        | -5                       | 2                 | 2                                      | -4                                     | No                 |
| cr.LP      | 5                        | -1                       | 2                 | 6                                      | 0                                      | Yes                |
| cr.MP      | 3                        | 0                        | 3                 | 5                                      | 2                                      | Yes                |
| cr.HP      | 3                        | -10                      | 4                 | 6                                      | -7                                     | No                 |
| cr.LK      | 1                        | -3                       | 3                 | 3                                      | -1                                     | Yes                |
| cr.MK      | -2                       | -6                       | 3                 | 0                                      | -4                                     | No                 |
| cr.HK      | 31                       | -10                      | 3                 | 33                                     | -8                                     | No                 |

From the list, we can see that Ken's best meaty buttons for combo followups are `st.MP` and `st.HP`.

## Combo Enders

Ken's magic number is +25. He gets this from three of his common combo enders:

1. **HP DP** - converting from lights
   TODO: video example
2. **Run DP** - converting from mediums or heavies
   TODO: video example
3. **juggle Run DP** - converting from st.MP xx st.HP target combo
   TODO: video example

For the purposes of this article, we will assume the combo is done in the corner, so you are automatically point blank with the opponent.

So we want to "link" our combo ender into our meaty button. How can we do this? One way to do this is to manually time the gap. But a much easier way is to use...

## Frame Kills

Frame kills are moves that are whiffed on purpose to help time another attack ([Infil link](https://glossary.infil.net/?t=Frame%20Kill)). In this case, timing your meaty.

**Note**: one disadvantage of using frame kills is that they are more likely to telegraph your next move. This becomes a bigger issue in longer sets or against good opponents who adapt fast. To develop a strong offense, it is crucial that you rotate through multiple different combinations of combo enders, meaties, and frame kills, to keep your opponent guessing. You can even consider doing "fake" frame kills to overload your opponent with noise!

### Frame Kill Calculation

Ken's frame advantage from each of the above knockdowns is +25. If we choose `st.MP` as the target meaty, `st.MP` has 4f startup and 4f active frames.

The formula for calculating our optimal frame kill is:
`KD frame advantage` - `startup` - `active` + 1

In Ken example above, we are looking for an 18 frame gap:
`25 - 4 - 4 + 1 = 18`

Luckily, Ken has a button that is exactly 18 frames total: `st.LK`
While `st.MP` is +4 oH and -2 oB, with perfect meaty timing it becomes +7 oH and +1 oB!

**Note**: in the above example, a gap smaller than 18 frames will result in the meaty whiffing. Meanwhile a gap larger than 18 frames frames will simply result in less frame advantage. For example, we can use forward dash (19f) as our frame kill, however it will result in being 0 on block, which means the opponent can mash their 4f button to reset to neutral.

## Building a Flowchart with Meaties

Since doing `st.MP` as a meaty gives us much better frame advantage, we can do `st.MP , cr.MP xx HP DP` which ups the combo damage to 2420. Very respectable! In fact, if we want to further optimize, we can do `st.MP , cr.MP xx Run DP` for 2660 damage, and it perfectly gives us the same +25 KD advantage as HP DP.

And finally since we are +1 oB, we can continue with a strike/throw mixup.

Our new flowchart now looks like this:

```text
HP DP -> st.LK , st.MP -> hit -> cr.MP xx HP DP -> repeat
                 v--> blocked -> walk up throw
                      v-> cr.LP , st.LK -> hit -> xx HP DP
                                  v--> blocked -> turn ends
```

Excellent. We now have a 2-layered mixup. But how do we take things a step further? Introducing our trump card...

## Spacing Traps

https://glossary.infil.net/?t=Spacing%20Trap
A spacing trap is doing an attack that is minus on block, but being far enough away from your opponent that if they try to attack you after blocking this move, they will whiff. You can then immediately whiff punish them with another attack as punishment for trying to take their turn back.

In our flowchart, we have the situation where the opponent has blocked the string `st.MP , cr.LP , st.LK`. While we are technically -2 and our turn should be over, we can take advantage of the specific spacing that we have created where most if not all of our opponent's options will whiff.
TODO: example video where Ryu's cr.MK whiffs

One easy option here is to use a wish punish.

### Wish Punish

https://glossary.infil.net/?t=Wish%20Punish
A "Wish Punish" is when a player doesn't react to a whiffed move, but instead swings wildly into empty space and hopes that the opponent just happens to get hit.

In our example, we can use Ken's `st.HP` as a wish punish and option select behind it; e.g. buffer HP DP (TODO: link), or even buffer a (micro) walk up drive rush for additional pressure.

The advantage of wish punishes are that they are extremely rewarding. A wish punish combo like `st.HP xx qcf+HK xx f+HK , LP DP` does a whopping 3070 damage! It is essentially as hard hitting as a shimmy combo.

On the other hand, wish punishes can be risky because you are giving your opponent a chance to whiff punish you. Also you are doing things on prediction rather than reaction (TODO: link Sirlin article about prediction vs reaction).

A safer (but less rewarding) option is to use a standard whiff punish, preferably on reaction.

Ken's whiff punish button is `st.HK`. Conveniently, it has more range than `st.HP`, and therefore you won't have to worry about whiffing it and getting whiff punished. Ken's basic whiff punish combo is `st.HK , Run DP`, which deals 2150 damage.

## Damage Optimization

Squeezing every ounce of damage out of every situation is the mark of a high MR player.

### Counter Hits

When our opponent mashes a button during our string, then we are awarded with an additional +2 frame advantage. So for example, our meaty `st.MP` is normally +7 oH, but turns into +9 cH. This allows us to link into cr.HP for a massive increase in damage. An example conversion would be:
`(meaty) st.MP , cr.HP xx qcf+HK xx f+HK , LP DP` for 3300 damage.

### Trade Setups

If we have a good read that our opponent will push a button during a specific sequence of our offense, then we can setup a trade scenario. This will sacrifice some of your health (and unfortunately the ability to get a Perfect), in exchange for more frame advantage and significantly more damage.

Consider the sequence `st.MP , cr.LP , st.LK`
If the opponent mashes a button between `st.MP` and `cr.LP`, then we'd get a (cH) `cr.LP , st.LK xx HP DP` combo for 1580 damage.

However, we can swap the `cr.LP , st.LK` for simply another `st.MP`, forcing a trade. This puts us at +7 oH, allowing us to combo into `cr.MK` which is 7f startup. A good conversion here would be `st.MP (trade) , cr.MK xx Run DP` for 2580 damage, a massive increase!

The disadvantage is that this can be normal specific. For example, trading with Ryu's `st.LP` results in more pushback, so Ken's `cr.MK` whiffs. Instead you'll have to link into `st.MK` target combo. Trade setups can also be character specific. For example, trading with JP's `cr.LP` results in being only +5, so no follow-ups are possible.

## Putting It All Together

Our final oki flowchart:
TODO: Excalidraw screenshot

## Training Regimen

Start with a basic set of options, and add things one at a time.

## Miscellaneous

### Choosing a combo ender - Advanced

A lot of this has to do with combo routing and the decision making process that happens upon landing the first hit of a combo, or sometimes even mid-combo. For example, with Ryu, your opponent whiffs a DP, and you start your punish with `st.HK , st.HP`. Do you end your combo with HP DP? Or qcf+HK? Or qcb+K? Things get more complicated when you're willing to spend meter to unlock additional combo routes (e.g. Chun Li).
