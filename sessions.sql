--
-- PostgreSQL database dump
--

-- Dumped from database version 15.2 (Homebrew)
-- Dumped by pg_dump version 15.1

-- Started on 2023-03-04 11:08:47 EET

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 231 (class 1259 OID 16834)
-- Name: sessions; Type: TABLE; Schema: public; Owner: timmy
--

CREATE TABLE public.sessions (
    phone_number bigint NOT NULL,
    dc_id smallint NOT NULL,
    api_id integer NOT NULL,
    test_mode boolean NOT NULL,
    auth_key bytea,
    user_id bigint,
    is_bot boolean,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sessions_api_id_check CHECK ((api_id > 0)),
    CONSTRAINT sessions_dc_id_check CHECK ((dc_id > 0)),
    CONSTRAINT sessions_phone_number_check CHECK ((phone_number >= 0)),
    CONSTRAINT sessions_user_id_check CHECK ((user_id > 0))
);


ALTER TABLE public.sessions OWNER TO timmy;

--
-- TOC entry 3666 (class 0 OID 16834)
-- Dependencies: 231
-- Data for Name: sessions; Type: TABLE DATA; Schema: public; Owner: timmy
--

COPY public.sessions (phone_number, dc_id, api_id, test_mode, auth_key, user_id, is_bot, created_at, updated_at) FROM stdin;
0	2	4277770	f	\\xbbc6b078d7bd70aaf0ba00d39bf1c4ffc52a47138b6b8d27f038e2c4de82e22adefd3df6b25da716dcf3d16a6176b83e6be1bfcc3558891a87f05636bef6284b6a8f756abab199fbfb0f88d4e7544055eade0453f351f217241b56855fad59a350db250d6a0fb5dbd3eae0b9f5c622dfdf471b341b47b606770b2656f53d3296fce79c740e14c5d2f7e90807dbed5c0291b4baeff99a2e2bce1bbcf7f4ea7fbc8de7ced8db2ceb0082bed912f2d1949403ac78246e8e181f5508084326135b26378368294ca0df87fe4558cdba66bdd1e747f853be3149f8289b25dabdf92d0338a9aefb05e6d1b1ceb442c1333118dd85e3a877be78965370f0f1a3ff81b0d5	5334726164	t	2023-02-22 18:21:50.05807+02	2023-02-22 18:21:51.155612+02
37129782350	4	4277770	f	\\x9959cdbe9cf1ad80fea3d8e1558dff3aa1076f79b632e3cd00c5d21eea9bae2f9141c2ea501add4b87329104887e6b1928bc17373ce0b27d0ead79db6a9d9df62bbf18732c0d91a2dcabead8eb727060535590f7c991c1a972c759b4884d9aa390d93d62729535ed4d7523591b1f824d12168520b303c234f09a38f7f7569c54fc68e8341ed8870b66b01a44f439bc3b6e496a4e036715cba596dcccfa92110fd5121d8fb690411974d064d40441c02ca560b0c91ce34fd045b321b1246e1940e06dde281fb30fed1d61ebbb1ec1c90a125db0a14def56c785c7ba3f344c1f37556e9decedde8f1230d74bf1ef40cdf25943302da83fa1cf627520b18a5d0da0	6138267637	f	2023-02-22 23:13:06.629053+02	2023-02-22 23:13:21.447145+02
918219960161	5	4277770	f	\\x1bd615636da2244a31cc995b2ef7e99dcf100dc2cd65e60d2b46ec2ed7c732b6e0ee4f1541ef3ba35ec5749989bc7016d6f2636be3db10e11b096348fa671acc26490e45fcc450bb01c25ebbed0a74392d3601ceb781053c84c0126afbbd6b31522904595a0117a0eec166f27d66f706823fd3e4be59bd414498ed2e5c5165a004d84469206b53c0ad4111925e19658c1b9bb290b9dbc9c6b2f29eb9080d429e4a4cc096fc286246e1db7012e2a14cd3f5a126f4e00e5118c26085d4f93d5ea6324024e1077483379313cf17ea4d541384f7a13a4e43617499cf3cc643ed79757e548fa8e64230e19ed79430773234da9aacc9e6420d7f675d1800ffc8d2d386	5821541866	f	2023-02-22 18:25:16.69704+02	2023-02-22 18:25:36.151459+02
918341656439	5	4277770	f	\\x243ecdfd6fd0fa0b6c2497ce235dd3e0335df62687d8bfa967e7c8be38cec718d7e7bb66bc92db8dc7239dbab0e91f0ea0566d6c7f20da82a7146e24595e90421f2c1313719f79711dcbd6bb4936b8da5533b67d49af0bd16a96635972b633d726dbe4d01c61351e9e11ce73f59004073d05609bd32a429da9795dc165a295854cde9c466ba5610c5bc66264d6ad6307b08bb6a20c707a2a58d0189d443b23c8944d5ec61965a3c0851e04ffdc0678380bda5d1660bba0731b595582c71776405e6e006a3cb4dc476c1be509ff31ba5dd62345a217c6c5fbd149ab7d014fb595189a4bf836f132c5fd2afe76fc1eedfce3bbf7d7efafa80b27a99f47e2e9de23	6074979998	f	2023-02-22 23:09:31.270729+02	2023-02-22 23:09:48.004135+02
37124932438	4	4277770	f	\\x7fe41f45cc0afd8752914faf4d6c6e39445e54f16a4b997f109e139a531983aef467b34c39c0ba052a80a6f72debbbc7e142a73d1ebdf70a832f6c0ce201b2c529cce01282a3b1197f285a369c6abf7289b2434230f9ff09aced75f6f1dbd45483826fc06271c7b8c68b7c06eca4bb1ccb4e8d1b241a9056538836a437118c406f11133e709a38fd8f9bacf61f8245b0b945a017f8083f835c4a291f51c8111aa209612856bf06c282294d8ec354c594cf16708d872913e52da5c088703122634c8e41fdc3eb70eb4f1e7157ffe2ac39ac6bbaf0bec1c9280378730e5b56079f70a5f232b2a629af3762ea9dda101de81ef91ff9759665b34499f36332ad8858	5969766339	f	2023-02-22 23:15:24.358668+02	2023-02-22 23:15:45.159391+02
917581067635	5	4277770	f	\\x59903b96e00f3bba166074b0a2c96d33a1e54a5b178a792a65d9941130fd3f22bed8443783d94699dd97eb75e49a16691d754fe06ec1e77bb5bb4fb2d8e07429391667e7a2b9dbcd302a50dc6a4c5e82bde0941727bb00edecb9070723db1b9059ac47a983e7c788f017bcbb97e02124ce52ffcd3411a625c632cb29f02da11363c88a3bb7711bc5976670a7dc2199789cab7133eecb7af682f62ba91313b4e09bc32f4fa99d649fc303d3611a714e77b15e381fdca2fba4f78d8e5ffb7b177237fb504fc2f696d93d5685a9044f839784ab4a84b6b83b6c9ea679005b8640fe4f42a49d6c283cdb6e6155656d6075a62a773e5659ecd7c4d236ce3b92a3047b	6239159287	f	2023-02-22 23:00:51.602585+02	2023-02-22 23:01:09.250397+02
919828387563	5	4277770	f	\\x3655a8b0cc6e81f24f28e95182512f9edcc08845d3ade52119d8e904ba93f9e9977c8dee537d46f8203437fb8f88c31f1cd17d120dabc97691238bbe877198ce53744fe06b89c5ebdb2b4b714bb0214f59530131cde8cff9109b5739756e2606a12fab225aae4ec15ceef9540482c8ab5a037a506e7dc5a166d4bd8610d7786efb57b9fd71312712c78375194d29c5c5363e08bb1bb1d180895818960212ac2fa4fe9c8bc6a5fc709442c5a60f87c1cb0e7216320b94d21bf2e355d5ba0eb9c88c53550129881217a62d39c51986c517de0fe0aa13f7031f0dc6c0dccb43ff994c87ec970a60cfb49a2d99894601239216b7dd19ec2c6857cae1f1ea1660759a	6049482232	f	2023-02-22 23:19:33.195864+02	2023-02-22 23:19:55.2331+02
918305530870	5	4277770	f	\\x167fc6586ee480a55b1f8eb1855677c551ecc198e29de790586a066624c6036d773235d02a96987ebf5d3fde6b4f6479d5dd4e8ac176c8a3a1ad0852760facb62ef191c3b2557125b4e42b4438ca79144b55c04b4982e9323a3b038a1f418275ef1231d8fe7c098e2b4589a237911d894a71dbe6bd09c968c2cc200556d5a1fd159f5a335d4de60c46d505551d9683d758e33ca8849afcfbb4e799ffeb046c57b34dc0e1dd48984ca5f021f406d1e66823adab0c12f9743a468a379995dd1b571e8c1c4287d86c6b71a9f593a519224df1bf1f389c4c0bb58c6a35924f091a13f525fa33224133a0e41c2bd886f47e9e146d0fb37f8b7602c1bd103c9c16fe38	6078210872	f	2023-02-22 23:08:37.950381+02	2023-02-22 23:08:58.005883+02
37125277304	4	4277770	f	\\x83b8e753f8023eea5ccf6fda3b673f62d7111601e2ac36e3e158cdaa5d1e9396ec94df613a055be2dc8e7b047c1382efed61dd2868954d8d71134788088e69c96e56b46d1af7f431d56436e5727a4ffd0a86fce75bc52226f5fe47dcf4048a61c3b903b3e02d810546c44138ff0d72136262ae10f58c1eeaf36a56ebf46cbdd9e6e1a21909c78bc7a46faabe6ccd28c65a04b85c5c4592b3db8c78e9f6470159cdfec05bfa47bfbde04271d99fa93780ece1104a6852700a1ddd7bc92a9c5d0d8aed42c9aefa1c9caac3690d2675f080d21c37b30561bc2423c28cd02543b68c4280bbad9168225c2cf30aee0febdfe1da5ed7ba7dcd7fad13aa8178160db82d	5922525308	f	2023-02-22 23:14:12.375687+02	2023-02-22 23:14:29.459844+02
2348124253457	4	4277770	f	\\x854d93c8197f6e68eb68cfc110d00542619fe17fd7b286c9e3513b921aaebbd867697df2d8c2569061874dedf2ca8be06d8e07b398dc662bf9c3c10fb51728481fe99fc270db1303be804e0580dba7308997f153b1e3807a8c0e29a29b324c67d21645fd2be664463710acabc3cb97e95f528adbf25ef6092a30520e72bf4e569efc2918432febacc232b2445497edd6a9f10d5457a642e7d5ce0255dc3e738c1d623b4b7e779dda94b6b11df09ef2d79f5a04312e92b9e35d3fb988aecefc1bd3537413edab2cf6baf97dca878245be945ca6d1d147e001c8a0bee78e481b01d899a5f6d65db7e828d3223cb63471343689be2ddb196f5e03a0eb3e100f84e1	6246610728	f	2023-02-22 23:16:44.292017+02	2023-02-22 23:17:02.474379+02
201007691941	4	4277770	f	\\x88dbf45975b0c99d9c38e6f57f0dbd2ef3caf0654609c41b5e7e5cb0b3a2fdb688d40b3c89b32b77562ee00b80c5c702ae3793e1db30d295de36911e6cedd55ddda14a25ce87fc044e5e5a02085cf297a5ae46c79331e9d50e77aba637686b5f66d8c1757cc55cf5aeaef2ed84acb0170af1f1e9a9a415b379151ee5a273ca55d73be839dbfb191731b5f87c7b57e9b130b9e2252e38fb3264d5f66eda7c7cb7ca1620705f6b3b0a9e8999f289724f74545ff1d0b5707bc390e655c41f7d9eaec885498a40a54fd8c63247fbb53816d1cde8784c6a9071d8fc8d1ea83d4995234fcf4df60138dbb62fc6ce9d13c2e31088db9330663e8b738903e1ec4547da15	5473691959	f	2023-02-22 23:16:15.647835+02	2023-02-22 23:16:31.567359+02
212651987818	4	4277770	f	\\x30e37aa95532afa394845be3e00bb7ba11cb05f943227103e2eed2bcdfa084435c9d77d4afbf21de591da5eb7cd2395c19ee6b75747d4b68514d2be4b7304d34dcfbcbf8e2e6a910937921ddd083cb60e1a427ba717bac10e0c6b37d51153ebf632f6f1efebf6448c063d67585b550e790e622ca1da0d07eee1cef5a700eed8861b5cf4f5f251611a3a3798ed38fc8b70fe619df7ecbbad026aebf7e89d876adda328c4dada9f8cd4825d1c56a13a6a7114974b7016e4c220ef9c34b5ced22964c3fd45931c428dd483f842338c32d2ece22f3233e69d0c651b982d85d982837ee57d81a429ffb3c3f377bc7e117fd1a6233623ed7352cb5c0c2ff5d82a02376	5937192823	f	2023-02-22 23:18:39.15218+02	2023-02-22 23:19:14.384142+02
201114663941	4	4277770	f	\\x533ffbf3bcaed064ca0b14d0b0fda98641c3d10382e82b23bdfc0e55a7c2f143835ba27cd14351e4b91a9b44575ed49d359ff8cad644ba8e2237108df2f41a311ffc3c0abed56bae8d5c6274795fc4e867a30f2ff674597d079a8f224a70c066ffb28fc8002df03c26031f389cbe2b41abe72dbfd1a158adcd03ddfc99664d9a9fcf44be137b0da0cfda4e1914bc40a63ddbe95096054d3ca1eb7ecb622d9f9635754bc9fca547a95c2927c664d97c33f023515562528d43438b3a78b0b4b0d8a807841d83476c592ff0ab37c8a0aca799b4d10a0504417f1b15d2d404f00472d4d1de0f8a2174ea88c82d528659c4a9f57375b5a8c999c2da7847a813895cc1	6152268661	f	2023-02-22 23:17:26.38178+02	2023-02-22 23:17:42.36264+02
543755447495	1	4277770	f	\\x92d19a19739ff5801891dfff87f8a8ffb7cc872ed0ad9a611a651377927b6983e2dd1efae9c77af86f88249f81c79ff170ca3125e41669af488bb6b6483ded9cb5c05ef409d980cfc52716b49b1e51551498b81b83aa6c73862ba6f5e8e0aba28bc78fe35c95436c44e3b6cd27b0eb93dc95232b4e2c4bacd74b3876e63e2f1c6fa0b7f9e126428342ffd55ffc0b86ca14b94545185665d7e214bbafc4748a3e8c5e47edd89b501c61107f55442519e7031a572358b735de8212213cbc666a767b98292d99a743c8e5a0fd0ad3d6c9cb9929e405e30401615ef88312040b71900b84d064632acf5709eb2c07dd7c76cceec5e249c7cc1122496d85052aee940d	5632255811	f	2023-02-22 23:20:13.880786+02	2023-02-22 23:20:51.702879+02
201050816626	4	4277770	f	\\x835fbb6b40ab680d1be322cf921c758c24797a9cf607315c37aa1ac9b60c8a1df4acbabe1c872fe26213663ea53a40b4421e2b765c81ab9a9c222180770ff1e26f396a4bab17443a56098e7b190e1dd4dd9a9f28b9e43a0770f5d5b52792b498d0cc5c7323b01a11443694cfde2a918847779e3b573e02b9e1bf3b05b0dc18f341ab0140c7b99be8137b35bae7d32ec470427823b53dcc3aab02a87fa75d300c389e909782f4a03540e3cc6f6a8e1483a09c34e05ae2abab41a2c91e4f5147192ed1fdde316050acc65f9d3b50b86179148aa1276adf25501bc14bc409456f001d7901636803c93d19376fc9b4f832bbba7253203ce4498fbe2e5eab454e4327	6068102317	f	2023-02-22 23:24:57.657231+02	2023-02-22 23:25:21.328372+02
201157636602	4	4277770	f	\\x752ecbf023235e962dcde0a0f49226bd78442b9c949a1d5a7440bde14180117766c71ed8ae97745fa95d2dbf62e3b0894974c5ea895d3c4c0735472a175be7109c667b33902489bc41253d17536c160d63d01817f8c54456e1ed5960263a4f745e701b6eddc92fa3aa253f596775a011302ae9f4d04ec5d22d39e5927f12b8da55407756e503b20ee9b325c1b202ef7ae63268391c19a82dbc1ac619477a62ab21d9494543ff04c3a92ad29591d0a6658cbad598f923d3a9b745f3ed4a4e05e635c54e9e394761013658dbd7a540c00b47e23384e080fb67310797c313936def3ff74883c5a660f3fcbf88b599efb98132b1cb1ac30a5187df5065ed2d9a16a3	5990150824	f	2023-02-22 23:25:33.846582+02	2023-02-22 23:25:51.515103+02
201111421096	4	4277770	f	\\x892c75cacefd3d64e3b64a6836348f2eaab18250c51635a6b35589648caf2b05668783f827b6144ffbeff60315926878551e456c8e6cc70086dcf0046a1fd01b9a6dbf89bb86a0c263dd6afd9c2e2beee405124b1f0ebcb0eb601d6c1d8019a4d8d6adc5bcad4e91a609dad7b05fa12016efe01a3f08d4c810c22a885b9e3c3f2b99e72799bf56bb7f3f74ef5286a26f9635f305b234001d55aa2abdeb9c1fa174c11c294849496fbd40fc7ea321cddb071b5b78029ba87ed86b983196a5c0f4498e2f4fb86082972b1c8963c825fa393ce0c276b8a485cec03c2a074b22bad3eba428088d0620d40ccf3b3fee5b3896ccb4c9379fe51f5008022269e81572c9	6210677375	f	2023-02-22 23:26:25.434813+02	2023-02-22 23:26:48.072442+02
918347267169	5	4277770	f	\\x5d263c2456deca6f3cc471def6831a2f76d8adb0b071109788badef93f0a2059d6101a2a23bf4c5b2ab9c3906134ee2f467d868381eb78308feb80e4ce7989d9a9df50ac7c627a21c6ec07f256912588614a77e3d38b9893f89221a30aabd5b1f0fec4b3a098583980cd8f38039f60a0f202b2d34b269fe136b2b12b49c0563b4606b60db97e53a26a2d014253f56a031ded3e9c6e7727f36a0af9cdf500ecae8cee4cd37139120b9c9553e9383b13bcd6f5c376926e65889f008f7a2084b94ceb815e3cc337297bcb29e338d25ca9da21c6e4330ce7cb638fefbcf77a610d43faf3fc32995cb6fef26635b5e10106c365099096938740d6a19e174947961522	6041144091	f	2023-02-22 23:26:59.922842+02	2023-02-22 23:27:24.815977+02
541159697057	1	4277770	f	\\x612d3f70fb36f29b8c2891725d794bf2d1dd04bdd84d3f0cc60fcc38d5dcbc802bc6218a95c76444f07c5a5891166ea62ccf6c6b3f4e1bbce156bbc4e559f4c53192cfdd1f1bea583a5f5e90e2d75509ac8335a0e966ab2656acb4e73066a4dcf0659bdbc8c67f3bbe28bb8dd05e466f1900539448c64ab1c09929a9a396139bdee8e3f4c34db870c9dc94a818cc1da56852f3a893f5f15c3a73ab6e7755e58cbaeff1fc2c51207b8a1f51a07f2ab329d93794a0dffb9782946256ffb3130d77672665608cfed1c7911ccbb7101fb9d66dd23d6bbb8c76f87ab75522aaf1a7012364ec512e41ff07fd24f45a020bc44fdac729f6b1dec8117056473e183407e2	6051969245	f	2023-02-22 23:38:53.737538+02	2023-02-22 23:39:32.759707+02
380683980524	2	4277770	f	\\x65f552a7d9e8383e43509e5f098ce79550fb18105f50f348449813bca0a6e9892420a151eb74e2238add1bf05523934aa6605eb98e03ad2f494e150c45320e55bd064ca94049e695e34abae6f1fa8037a372495bb8570b74ae9b750fe75e5ecfb90a466563efdc53e2e56a06a32c5fb28ee6db8493104f29bd2004f23facb97cc6b0ad4d34c2094d04ad9c68549833d131d2c4098ae31404f1452ef822b06b26adf3d656a0e2ac937bd81d647e33379a15fb249288923657c3a8ef5db01ef1fcbfdb6c3daf62787b2a794aa6517019b27d9c3652a62bda3e0d228afb6c4cc7b3950a0babe5daeafa1eab03c4d096c6e2b2de0cee7d552dd91164cb6be7b5826b	\N	\N	2023-03-02 17:31:50.445683+02	2023-03-02 17:31:51.474936+02
681306167	1	4277770	f	\\x3a2c3123d6c669a9b9ae67fb898a0b35e4f9d91015e7fed5dbc56f9a375cb7cfdb7c9e64f78332055708b25894f5ade4ce882c10d546773738a0765c1a266477adbd0983ab9d11d7dad7567c083ba0eeb43d50f1794db868dbfaa7ebc973cc82cf197cdeae060bc4608dab4c68d19b94279a8a3d91a73e980507726c89cc567f1830c7de58f39266379bd62eda3381bb5de33a2722047a2c6875d6b131fd798075ccce802347222d56fd2e70609776487c7df8ec741b260ed395845a03ba277879d74d61f585a17b65d44bb193f431dd4c78cf507dec8df2903b4347948e188c56cefd8e14ea3107c19fa68833e44df21d7669aa36ce1ecf8d73872eb9cf7865	\N	\N	2023-03-02 19:36:41.207627+02	2023-03-02 19:36:43.975658+02
380957573442	2	4277770	f	\\x1ab415796bd66b08a6633d1797f8fe1b3c82b0228f6ee5ae2d8c475592b98f785868d50891718fe1aef489291c8b3a954e32955d82e5a106fde89268aa6dcc724ea39525b02ee6ffc5cb60aebc418e969cad59925938b5798555e062b0faab92512ae468a20d9c6f696a12b876527888da862c1263377d638b6c4e02bb58604e806efaa29ace002330e58787e552494ee3e717f74e5be888646c692899e047ebf1524490144182e6d9d9f745b7d420503bae318cc5d9efd81cae1882a9e331b2b81ff6dbab96203b6e30996cec466e58357c23264f3a1b14e62f64957886aeb5d3857f8e43b36d77ddfa725216869b25dbeec0c7eb083658565cd5bb0febef3a	5491577707	f	2023-03-02 19:38:46.842376+02	2023-03-02 19:39:36.009488+02
380681306167	2	4277770	f	\\x563d831873a4580945dfd10294d69a1fff2d5d08d8e2b17352d20cedd1849f62c51bab8805082416050a7d5182b6d091cbd76514d98aa749eb45d079c703202897ef9d33a3a650d9bcf34423b9c38e5139db5bbe4ccdea531bf7133957f236ca7d43241cef1e5b5b60265a68a4828c40e7fc2c7cf2377d195f241136215e32725ef51d7fd381c999eb49900b4bc23d43b176cd94a97aa142942742481807baf2f5ed7c195ee4858822bb2f8a7f736727913054b933b8c613259596795e4b80f962ba69143f14f28b9f39da8516cd5ac14426ebdc7ca45c2eeb4cae21a1faec591be1015c76e0a71f70b3faa8c3724fd1bce29a31cdb9784ff1847d0418283a5e	5530672537	f	2023-03-02 19:37:01.337294+02	2023-03-02 19:46:15.701937+02
380634162536	2	4277770	f	\\x99400920fa6044acd2cf763ed53eb086aa005b9d39110f58b7c1ba331722b72d3655609ae3a3e6a6469854a827cad2a4a1ba378616e35b3bc45b0bd3caa27cb30cc6dbdfb0e7b409de2ac83be35a418f476ceecb5aa900d5bf74a78b8b0b4e2b90fed21023b3afabd5c8213897c7dad7698521bc07c7ee770731fbeb6a2496c2e695ef4ee1ef48da7e16f2e6cbb0b7a568803c4af122e5f6f2f88e11f6e83134fa25e4cbb1542641a60b65809ecd3b920ae8d73dfb870c1dc0f797d5fd99db0cc58c473f105a07afa6873f950d243ea4796f90f3f50b426bba367dd2d4f03cc0a744dcbe296777a73370d0619e1e096659553a1ee19b7febce14a93dd5007c03	\N	\N	2023-03-03 15:12:01.132301+02	2023-03-03 15:12:02.130186+02
380634162539	2	4277770	f	\\x605f1dfe0c1efbbecaff10498585937a7fc953bcc3c7a64a89d38059452ac52184b67cfb5be66fcd70f98ff72928c7d5fcb4caa118c101b27078090e405ccccdfa670e234c13d58fb091b84cbc0ae8cb27329ea9cf2377484cd97c2fd64c5f67a5edbc59ad3eeba2cc8818bd470268e85f73f548d26bed11971356cfc3d5977aa3a93dd68e8002c2428ff6c2be2c9c8f1829d4b04ffbc736304a0e9442a84e2ccd2c1b2e636e46635cfc8fcb742c2a3ffc8711a300ee92d773ca5a967d2075ece7e4ca0e54bc03e4d23516912aa833116cbf3fa2ac29c418c5dbbeef1b1bb482293340a55f5b7449853f29029c1e5404155371cdf64ac44cde4f02884079b427	5329163345	f	2023-03-03 15:15:15.856172+02	2023-03-03 15:15:33.652367+02
680888147	2	4277770	f	\\x6c28d9f89378536dfd4e1e3552b0bd8158f30fe969925c049696121d2b95014ce498901df49119e5da7f431b57c98dd648e0202b09518ae67f116e1d0114fbeb097b9843e1c30ed4fb28e422d27339f9e3e728148fd33cce7f19eead837a95da42dfe882cf53285dca029b5c5e4f5a84f81fde7b43d31662420fe3a71db7726200cbb43527a99d9ec62984c41fa81c74b9e5de05a844d3377da1d7e2739adfe3ee7e14553a821c4565c2f414a4f9d2bfbe984d9666dbf8ac4b557cf3db0bf026ded61f6abfc2cfc030a744365590fdb8707fefaa68c2885cb96873f2e6ff95895520d3ea46f840da50e6db890f072cafa2c5a00b6d11c3af659d5a7dc843687b	\N	\N	2023-03-02 20:17:29.408302+02	2023-03-02 20:17:30.395372+02
380680888147	2	4277770	f	\\x7a380b84cc1f8ea01fecb35e03e5a81d1e1ce2de761237c3f29d1c223c0b047c50dda50e1a85e4249fee7275498392c4b53f238c09fc468c08ac1d2a0fe11e8a1968facf709174f29365bd68f4df0cac9e1f8fd0ffc8a77f501a65eade1984f54d7161f1ab3944149cea9d6b3708775a7b46dd6294d3eaa3ec7a9a5d89e47f0d1e9f4576e8da584b321068be53b14f7b1c806e9e96c0930cb75f32252f87c99dfd3559f188df26063c2618c469a461d6c4b14dc64f42b3c6d0e4df8663256b264629ceec487664a8d8ed358addc89d503bb85e4546e704e0911e6eade8cd7a878a2bfbc0147cf89089a1e282dcf3efa1e7eb4ece73843de80e10d711c06fdf71	5636692472	f	2023-03-02 20:17:37.033433+02	2023-03-02 20:18:00.939976+02
\.


--
-- TOC entry 3521 (class 2606 OID 16916)
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: timmy
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (phone_number);


--
-- TOC entry 3523 (class 2606 OID 16918)
-- Name: sessions sessions_user_id_key; Type: CONSTRAINT; Schema: public; Owner: timmy
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_user_id_key UNIQUE (user_id);


-- Completed on 2023-03-04 11:08:47 EET

--
-- PostgreSQL database dump complete
--

