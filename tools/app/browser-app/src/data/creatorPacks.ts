export type CreatorTarget = {
  name: string;
  url: string;
};

export type CreatorPack = {
  id: string;
  name: string;
  price: string;
  priceNum: number;
  currency: string;
  count?: number;
  countLabel?: string;
  description: string;
  badge?: string;
  disabled: boolean;
  targets?: CreatorTarget[];
};

export const TOP_50_CREATORS: CreatorTarget[] = [
  { name: 'Sơn Tùng M-TP', url: 'https://www.facebook.com/MTP.Fan' },
  { name: 'Đen Vâu', url: 'https://www.facebook.com/denvau' },
  { name: 'Mỹ Tâm', url: 'https://www.facebook.com/mytam.info' },
  { name: 'Hồ Ngọc Hà', url: 'https://www.facebook.com/hongocha.singer' },
  { name: 'Đông Nhi', url: 'https://www.facebook.com/dongnhi.singer' },
  { name: 'Trấn Thành', url: 'https://www.facebook.com/tran.thanh.ne' },
  { name: 'Hari Won', url: 'https://www.facebook.com/hariwon.official' },
  { name: 'Trường Giang', url: 'https://www.facebook.com/truonggiang.artist' },
  { name: 'Nhã Phương', url: 'https://www.facebook.com/nhaphuong.actress' },
  { name: 'Ninh Dương Lan Ngọc', url: 'https://www.facebook.com/ninhduonglanngoc' },
  { name: 'Khoai Lang Thang', url: 'https://www.facebook.com/khoailangthang' },
  { name: 'Ninh Tito', url: 'https://www.facebook.com/ninhtitovlog' },
  { name: 'Vũ Dino', url: 'https://www.facebook.com/dinovuvlog' },
  { name: 'Quan Không Gờ', url: 'https://www.facebook.com/quankhonggo.official' },
  { name: 'Bếp Trên Đỉnh Đồi', url: 'https://www.facebook.com/beptrendinhdoi' },
  { name: 'Duy Thẩm', url: 'https://www.facebook.com/duytham.official' },
  { name: 'Vật Vờ Studio', url: 'https://www.facebook.com/vatvostudio.official' },
  { name: 'Schannel', url: 'https://www.facebook.com/schannel.vn' },
  { name: 'Đặng Nam Hải Triều', url: 'https://www.facebook.com/haitrieu.schannel' },
  { name: 'Tuấn Ngọc Đây', url: 'https://www.facebook.com/tuanngocday.official' },
  { name: 'Độ Mixi', url: 'https://www.facebook.com/mixigaming.official' },
  { name: 'Rambo', url: 'https://www.facebook.com/rambo.refund' },
  { name: 'Nhism', url: 'https://www.facebook.com/nhism.refund' },
  { name: 'DJ Chip', url: 'https://www.facebook.com/djchip.refund' },
  { name: 'FunkyM', url: 'https://www.facebook.com/funkym.refund' },
  { name: 'Changmakeup', url: 'https://www.facebook.com/changmakeup' },
  { name: 'Trinh Phạm', url: 'https://www.facebook.com/trinhpham.beauty' },
  { name: 'Chloe Nguyen', url: 'https://www.facebook.com/chloenguyen.official' },
  { name: 'Cô Em Trendy', url: 'https://www.facebook.com/coemtrendy.official' },
  { name: 'Hà Trúc', url: 'https://www.facebook.com/lehatruc.official' },
  { name: 'Theanh28 Entertainment', url: 'https://www.facebook.com/Theanh28' },
  { name: 'Beatvn', url: 'https://www.facebook.com/beatvn.network' },
  { name: 'Insight Mất Lòng', url: 'https://www.facebook.com/insightmatlong.official' },
  { name: 'K Crush', url: 'https://www.facebook.com/kcrush.network' },
  { name: 'Không Sợ Chó', url: 'https://www.facebook.com/khongsocho.community' },
  { name: 'Shark Phạm Thanh Hưng', url: 'https://www.facebook.com/sharkhung.official' },
  { name: 'Shark Nguyễn Hòa Bình', url: 'https://www.facebook.com/sharkbinh.nexttech' },
  { name: 'Shark Thái Vân Linh', url: 'https://www.facebook.com/sharkthavanlinh' },
  { name: 'Shark Lê Hùng Anh', url: 'https://www.facebook.com/sharkhunganh' },
  { name: 'Shark Louis Nguyễn', url: 'https://www.facebook.com/sharklouisnguyen' },
  { name: 'Khánh Vy', url: 'https://www.facebook.com/khanhvy.official' },
  { name: 'Spiderum', url: 'https://www.facebook.com/spiderum.community' },
  { name: 'The Present Writer', url: 'https://www.facebook.com/thepresentwriter' },
  { name: 'Hana\'s Lexis', url: 'https://www.facebook.com/hanaslexis.official' },
  { name: 'Dan Hauer', url: 'https://www.facebook.com/danhauer.english' },
  { name: 'Việt Phương Thoa', url: 'https://www.facebook.com/vietphuongthoa.official' },
  { name: 'Tun Phạm', url: 'https://www.facebook.com/tunpham.official' },
  { name: 'Long Chun', url: 'https://www.facebook.com/longchun.official' },
  { name: 'Duy Khánh ZhouZhou', url: 'https://www.facebook.com/duykhanh.zhouzhou' },
  { name: 'Trang Hý', url: 'https://www.facebook.com/tranghy.official' },
];

export const CREATOR_PACKS: CreatorPack[] = [
  {
    id: 'pack-50-free',
    name: '50 creator list October',
    price: 'Free',
    priceNum: 0,
    currency: '$',
    count: 50,
    countLabel: '50 kênh',
    badge: 'Miễn phí',
    description: '50 nhà sáng tạo nội dung hàng đầu Việt Nam đa dạng ngành nghề (Âm nhạc, Giải trí, F&B, Công nghệ...) tháng 10.',
    disabled: false,
    targets: TOP_50_CREATORS,
  },
  {
    id: 'pack-1000-bds',
    name: '1000 creator bđs November',
    price: '5$',
    priceNum: 5,
    currency: '$',
    count: 1000,
    countLabel: '1.000 kênh',
    badge: 'Sắp ra mắt',
    description: '1.000 kênh Bất động sản, môi giới, dự án, phong cách sống & phân tích thị trường tháng 11.',
    disabled: true,
  },
  {
    id: 'pack-1000-daotao',
    name: '1000 creator đào tạo December',
    price: '5$',
    priceNum: 5,
    currency: '$',
    count: 1000,
    countLabel: '1.000 kênh',
    badge: 'Sắp ra mắt',
    description: '1.000 kênh Chuyên gia, Diễn giả đào tạo kinh doanh, kỹ năng, ngoại ngữ & phát triển bản thân tháng 12.',
    disabled: true,
  },
  {
    id: 'pack-10000-tonghop',
    name: '10000 creators tổng hợp December',
    price: '20$',
    priceNum: 20,
    currency: '$',
    count: 10000,
    countLabel: '10.000 kênh',
    badge: 'Sắp ra mắt',
    description: '10.000 creators đa ngành nghề lớn nhất Việt Nam cho chiến dịch phủ sóng thương hiệu quy mô lớn tháng 12.',
    disabled: true,
  },
  {
    id: 'pack-maintenance-yearly',
    name: 'bảo trì dài hạn',
    price: '50$/year',
    priceNum: 50,
    currency: '$',
    countLabel: 'Cập nhật hàng tháng',
    badge: 'Gói năm · Sắp ra mắt',
    description: 'Tự động bảo trì, cập nhật danh sách creator mới và lọc link lỗi định kỳ hàng tháng trong suốt 1 năm.',
    disabled: true,
  },
];
