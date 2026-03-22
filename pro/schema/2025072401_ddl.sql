alter table weibo_note add column `image_list` longtext COMMENT '封面图片列表';
alter table weibo_note add column `video_url` longtext DEFAULT NULL COMMENT '视频地址';