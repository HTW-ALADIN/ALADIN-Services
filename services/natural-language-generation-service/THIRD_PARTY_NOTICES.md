# Third-party notices

## jsRealB 5.5.0 and 4.6.5

This service imports `jsrealb` 5.5.0 to perform English and French surface
realisation. That published package declares a `jsrealb` self-dependency, so
npm also installs 4.6.5 transitively; the service does not import the older
copy directly.

- Project: <https://github.com/rali-udem/jsRealB>
- Author and maintainer: Guy Lapalme, RALI, Université de Montréal
- npm package metadata license: ISC
- Upstream source-code license stated by the upstream README: Apache License
  2.0
- Bundled linguistic-resource license stated by the upstream README: Creative
  Commons Attribution-ShareAlike 4.0
- Apache license: <https://www.apache.org/licenses/LICENSE-2.0>
- CC BY-SA 4.0 license:
  <https://creativecommons.org/licenses/by-sa/4.0/>

The English and French lexicons and linguistic rules are supplied by jsRealB
and remain subject to their upstream licenses. No claim of endorsement by the
upstream authors or institutions is made.

## RosaeNLG 4.4.0

This service imports RosaeNLG 4.4.0 for trusted template/data-to-text
generation, including higher-level anaphora and lexical variation. The
project was deprecated and its repository archived in March 2026. It is a
deliberate legacy dependency used to provide the two capability families that
jsRealB does not cover directly.

- Project: <https://github.com/RosaeNLG/rosaenlg>
- npm package: <https://www.npmjs.com/package/rosaenlg/v/4.4.0>
- License declared by the package: Apache License 2.0
- Apache license: <https://www.apache.org/licenses/LICENSE-2.0>

RosaeNLG includes language resources and transitive packages which remain
subject to their respective upstream licenses. Their license texts and
package metadata are included in the installed production dependency tree.
No claim of endorsement by the upstream authors is made.
