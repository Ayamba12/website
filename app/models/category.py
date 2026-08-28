from app.extensions import db


class OpportunityCategory(db.Model):
    __tablename__ = "opportunity_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    opportunities = db.relationship("Opportunity", backref="category", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "is_active": self.is_active,
        }


class OpportunityTag(db.Model):
    __tablename__ = "opportunity_tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "slug": self.slug}


opportunity_tag_map = db.Table(
    "opportunity_tag_map",
    db.Column("opportunity_id", db.Integer, db.ForeignKey("opportunities.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("opportunity_tags.id"), primary_key=True),
)
